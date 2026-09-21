"""认证 / 病例库 / 历史记录 端到端冒烟（对应 Spec §11 第 3-7 步 + §8 验收标准）。

设计要点：
- **进程内运行**（FastAPI TestClient），不需要事先启动服务、不依赖外部依赖。
- 覆盖 Spec §8 的 AC-01 ~ AC-13 关键断言，以及 §5.2 的响应体追加字段。
- 退出码 0 表示全部通过，非 0 表示有失败项（便于 CI / 脚本判定）。

运行（项目根目录）：
    .venv\\Scripts\\python.exe scripts\\smoke_auth.py
"""

import io
import sqlite3
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import constants  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import users as users_repo  # noqa: E402

FAILURES = []
DEMO = {"username": "demo", "password": "demo1234"}
DISPLAY_IMG = ROOT / "test_assets" / "supported_diseased" / "Tomato__Early_blight.jpg"


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ::  {extra}" if extra else ""))
    if not cond:
        FAILURES.append(name)


def _post_image(client, headers=None):
    with DISPLAY_IMG.open("rb") as fh:
        payload = io.BytesIO(fh.read())
    return client.post(
        "/api/v1/predict",
        headers=headers or {},
        files={"file": ("early_blight.jpg", payload, "image/jpeg")},
    )


def main() -> int:
    print("=" * 72)
    print("禾目 AgriGuard · 认证 / 病例库 / 历史记录 冒烟测试")
    print("=" * 72)
    check("诊断用例图片存在", DISPLAY_IMG.is_file(), str(DISPLAY_IMG))

    with TestClient(app) as client:
        # --- 步骤 3：演示账号登录 ---------------------------------------
        r = client.post("/api/v1/auth/login", json=DEMO)
        check("Step3 / AC-03 演示账号 demo/demo1234 登录成功", r.status_code == 200,
              f"status={r.status_code}")
        body = r.json()
        token = body.get("token")
        check("Step3 登录返回 token 与 user", bool(token) and bool(body.get("user")))
        auth = {"Authorization": f"Bearer {token}"}

        # --- AC-02 重复用户名 -------------------------------------------
        r = client.post("/api/v1/auth/register", json=DEMO)
        check("AC-02 用户名已存在时拒绝(409)", r.status_code == 409, f"status={r.status_code}")

        # --- 修复二：IntegrityError 不得被无条件吞成"用户名已被占用" ----
        check("数据层：重复用户名返回 None（服务层据此映射 409）",
              users_repo.create_user("demo", "x", "h", "00") is None)
        try:
            # password_hash=None 触发 NOT NULL 约束（与用户名唯一约束无关）
            users_repo.create_user("nz_" + uuid.uuid4().hex[:8], "n", None, "00")
            check("非用户名约束的 IntegrityError 必须上抛（不得被吞成 409）", False, "未抛出异常")
        except sqlite3.IntegrityError:
            check("非用户名约束的 IntegrityError 正确上抛（未被误报为用户名占用）", True)

        # --- AC-01 注册并直接登录 ---------------------------------------
        uname = "u" + uuid.uuid4().hex[:8]
        r = client.post("/api/v1/auth/register",
                        json={"username": uname, "password": "pass12345"})
        check("AC-01 注册成功并直接返回 token", r.status_code == 200 and bool(r.json().get("token")),
              f"status={r.status_code}")
        token2 = r.json().get("token")
        auth2 = {"Authorization": f"Bearer {token2}"}
        me2 = client.get("/api/v1/auth/me", headers=auth2)
        check("AC-01 /auth/me 返回新注册用户",
              me2.status_code == 200 and me2.json()["user"]["username"] == uname)

        # --- 注册参数校验 -----------------------------------------------
        r = client.post("/api/v1/auth/register", json={"username": "x", "password": "pass12345"})
        check("注册 用户名过短返回 400", r.status_code == 400, f"status={r.status_code}")
        r = client.post("/api/v1/auth/register",
                        json={"username": "y" + uuid.uuid4().hex[:6], "password": "short"})
        check("注册 密码过短返回 400", r.status_code == 400, f"status={r.status_code}")

        # --- AC-04 密码错误不区分用户名/密码 ----------------------------
        r = client.post("/api/v1/auth/login", json={"username": uname, "password": "wrongpass"})
        check("AC-04 密码错误返回 401（不泄露账号是否存在）", r.status_code == 401,
              f"status={r.status_code}")
        r = client.post("/api/v1/auth/login", json={"username": "no_such_user", "password": "x"})
        check("AC-04 用户不存在返回同样 401", r.status_code == 401, f"status={r.status_code}")

        # --- 步骤 4 / AC-07：病例库索引 ---------------------------------
        r = client.get("/api/v1/cases")
        data = r.json() if r.status_code == 200 else {}
        crops = data.get("crops", [])
        total = sum(int(c["count"]) for c in crops)
        check("Step4 / AC-07 病例库返回 14 种作物", len(crops) == 14, f"crops={len(crops)}")
        check("Step4 / AC-07 病例库合计 38 个类别", total == 38, f"total={total}")
        check("AC-07 覆盖 constants 中声明的全部作物",
              {c["crop_cn"] for c in crops} == set(constants.SUPPORTED_CROP_CN))

        # --- AC-08 病例详情 + 例图 --------------------------------------
        class_key = "Tomato___Early_blight"
        d = client.get(f"/api/v1/cases/{quote(class_key, safe='')}").json()
        check("AC-08 病例详情含中文名/简介/症状/防治",
              bool(d.get("crop_cn")) and bool(d.get("disease_cn"))
              and bool(d.get("summary")) and bool(d.get("symptoms")) and bool(d.get("prevention")))
        check("AC-08 病例详情给出例图 URL", bool(d.get("image_url")))
        img = client.get(f"/api/v1/cases/image/{quote(class_key, safe='')}")
        check("AC-08 例图返回 image/jpeg",
              img.status_code == 200 and img.headers.get("content-type", "").startswith("image/"),
              f"status={img.status_code} ct={img.headers.get('content-type')}")
        # 带空格 / 括号的类别键也要能取到例图
        weird = "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"
        img2 = client.get(f"/api/v1/cases/image/{quote(weird, safe='')}")
        check("AC-08 含空格/括号的类别键例图可取", img2.status_code == 200,
              f"status={img2.status_code}")
        check("病例库未收录的键返回 404", client.get("/api/v1/cases/Nope___Nope").status_code == 404)

        # --- 步骤 5 / AC-05：未授权 401 ---------------------------------
        r = client.get("/api/v1/history")
        check("Step5 / AC-05 未携带 token 访问 /history 返回 401", r.status_code == 401,
              f"status={r.status_code}")
        r = client.get("/api/v1/history", headers={"Authorization": "Bearer bad-token"})
        check("AC-05 无效 token 返回 401", r.status_code == 401, f"status={r.status_code}")
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Token xyz"})
        check("AC-05 非 Bearer 认证头返回 401", r.status_code == 401, f"status={r.status_code}")

        # --- 步骤 6 / AC-09：带 token 诊断 -> 自动入库 ------------------
        r = _post_image(client, auth)
        pdata = r.json()
        check("Step6 带 token 诊断返回 200", r.status_code == 200, f"status={r.status_code}")
        check("Step6 诊断本身成功（未被前置校验/OOD 拒绝）", pdata.get("ok") is True,
              f"reason={pdata.get('reason')}")
        history_id = pdata.get("history_id")
        check("Step6 / AC-09 自动入库 history_id 非空", bool(history_id),
              f"history_id={history_id}")
        check("§5.2 追加字段 class_key 已下发", bool(pdata.get("class_key")),
              f"class_key={pdata.get('class_key')}")
        check("§5.2 既有字段未破坏（ok/detections/ood_score/prescription_source 均在）",
              all(k in pdata for k in ("ok", "detections", "ood_score", "prescription_source")))

        # --- 步骤 7：历史可查到 -----------------------------------------
        r = client.get("/api/v1/history?limit=5", headers=auth)
        h = r.json()
        check("Step7 历史列表可查到记录 total>=1", r.status_code == 200 and h.get("total", 0) >= 1,
              f"status={r.status_code} total={h.get('total')}")
        first = (h.get("items") or [{}])[0]
        check("列表项含 has_thumb（缩略图已落库）", first.get("has_thumb") is True,
              f"has_thumb={first.get('has_thumb')}")

        # --- AC-10：未登录照常诊断、不入库 ------------------------------
        r = _post_image(client)
        ndata = r.json()
        check("AC-10 未登录仍正常返回结果", r.status_code == 200 and ndata.get("ok") is True,
              f"status={r.status_code}")
        check("AC-10 未登录不产生 history_id", ndata.get("history_id") is None)

        # --- 历史详情 + 缩略图 ------------------------------------------
        r = client.get(f"/api/v1/history/{history_id}", headers=auth)
        item = r.json().get("item", {})
        check("历史详情包含处方结构", r.status_code == 200 and item.get("prescription") is not None,
              f"status={r.status_code}")
        th = client.get(f"/api/v1/history/{history_id}/thumb?kind=original", headers=auth)
        check("缩略图端点返回 image/jpeg",
              th.status_code == 200 and th.headers.get("content-type", "").startswith("image/"),
              f"status={th.status_code}")
        th = client.get(f"/api/v1/history/{history_id}/thumb?kind=heatmap", headers=auth)
        check("热力图缩略图端点可取到", th.status_code == 200, f"status={th.status_code}")

        # --- AC-11：筛选与搜索 ------------------------------------------
        r = client.get("/api/v1/history?crop=%E7%95%AA%E8%8C%84", headers=auth).json()
        check("AC-11 按作物（中文）筛选只返回匹配项",
              r.get("total", 0) >= 1 and all(i["crop_cn"] == "番茄" for i in r["items"]),
              f"total={r.get('total')}")
        r = client.get("/api/v1/history?crop=tomato", headers=auth).json()
        check("AC-11 按作物（crop_key）筛选同样生效",
              r.get("total", 0) >= 1 and all(i["crop_cn"] == "番茄" for i in r["items"]))
        r = client.get("/api/v1/history?q=%E6%97%A9%E7%96%AB", headers=auth).json()
        check("AC-11 关键词搜索命中", r.get("total", 0) >= 1, f"total={r.get('total')}")
        r = client.get("/api/v1/history?q=zzz_no_match_zzz", headers=auth).json()
        check("AC-11 关键词无匹配时返回空列表", r.get("total") == 0)
        r = client.get("/api/v1/history?crop=%E4%B8%8D%E5%AD%98%E5%9C%A8%E7%9A%84%E4%BD%9C%E7%89%A9", headers=auth).json()
        check("AC-11 无法识别的作物筛选退化为空结果（不静默忽略筛选）", r.get("total") == 0,
              f"total={r.get('total')}")
        # --- 修复一：crop / q 纯空白必须等同"未提供筛选" ---
        base_total = client.get("/api/v1/history", headers=auth).json().get("total")
        for raw in ("%20", "%20%20"):
            got = client.get(f"/api/v1/history?crop={raw}", headers=auth).json().get("total")
            check(f"crop 纯空白({raw}) 视为未筛选（不静默忽略、也不误报 0）",
                  got == base_total, f"base={base_total} got={got}")
        got = client.get("/api/v1/history?q=%20", headers=auth).json().get("total")
        check("q 纯空白视为未筛选", got == base_total, f"base={base_total} got={got}")
        got = client.get("/api/v1/history?crop=zzz", headers=auth).json().get("total")
        check("crop='zzz' 不可解析 → 0 条（不退化不过滤）", got == 0, f"got={got}")
        r = client.get("/api/v1/history?limit=99999&offset=-5", headers=auth)
        check("历史分页参数越界被安全收敛（不报错）", r.status_code == 200, f"status={r.status_code}")

        # --- AC-13：越权防护（404 不泄露存在性）-------------------------
        r = client.get(f"/api/v1/history/{history_id}", headers=auth2)
        check("AC-13 越权读他人记录返回 404", r.status_code == 404, f"status={r.status_code}")
        r = client.delete(f"/api/v1/history/{history_id}", headers=auth2)
        check("AC-13 越权删他人记录返回 404", r.status_code == 404, f"status={r.status_code}")
        r = client.get(f"/api/v1/history/{history_id}/thumb", headers=auth2)
        check("AC-13 越权取他人缩略图返回 404", r.status_code == 404, f"status={r.status_code}")
        r = client.get("/api/v1/history/999999", headers=auth)
        check("AC-13 不存在的 id 同样返回 404（与越权不可区分）", r.status_code == 404)

        # --- AC-12：删除自己的记录 --------------------------------------
        r = client.delete(f"/api/v1/history/{history_id}", headers=auth)
        check("AC-12 删除自己的记录返回 200", r.status_code == 200, f"status={r.status_code}")
        r = client.get(f"/api/v1/history/{history_id}", headers=auth)
        check("AC-12 删除后不可再查到（404）", r.status_code == 404, f"status={r.status_code}")

        # --- §5 可选端点：手动补录 --------------------------------------
        r = client.post("/api/v1/history", headers=auth, json={
            "class_key": "Tomato___Early_blight", "crop_cn": "番茄", "disease_cn": "早疫病",
            "confidence": 0.97, "severity_grade": "中",
            "prescription": {"disease": "番茄 · 早疫病", "severity": "中", "summary": "测试",
                             "biological": "生物", "chemical": "化学", "tips": "提示"},
            "prescription_source": "template",
        })
        manual_id = r.json().get("id") if r.status_code == 200 else None
        check("§5 手动补录端点返回新记录 id", bool(manual_id), f"status={r.status_code}")
        if manual_id:
            r = client.get(f"/api/v1/history/{manual_id}", headers=auth)
            item = r.json().get("item", {}) if r.status_code == 200 else {}
            check("§5 手动补录记录可查、结构完整、无缩略图",
                  r.status_code == 200 and item.get("prescription_source") == "template"
                  and item.get("has_thumb") is False, f"status={r.status_code}")
            r = client.delete(f"/api/v1/history/{manual_id}", headers=auth)
            check("§5 手动补录记录可删除", r.status_code == 200, f"status={r.status_code}")

        # --- AC-06：登出使 token 立即失效 -------------------------------
        r = client.post("/api/v1/auth/logout", headers=auth2)
        check("AC-06 登出返回 200", r.status_code == 200, f"status={r.status_code}")
        r = client.get("/api/v1/auth/me", headers=auth2)
        check("AC-06 登出后原 token 立即失效(401)", r.status_code == 401, f"status={r.status_code}")

        # --- 兼容性：旧路径 /predict 仍可用 -----------------------------
        r = client.post("/predict", files={"file": ("d.jpg", io.BytesIO(DISPLAY_IMG.read_bytes()),
                                                    "image/jpeg")})
        check("兼容 旧别名 /predict 正常返回", r.status_code == 200 and r.json().get("ok") is True,
              f"status={r.status_code}")
        check("兼容 旧别名未登录时不入库", r.json().get("history_id") is None)

    print("-" * 72)
    if FAILURES:
        print(f"结果：FAILED（{len(FAILURES)} 项未通过）")
        for name in FAILURES:
            print(f"   - {name}")
        return 1
    print("结果：ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
