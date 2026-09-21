"""认证 / 病例库 / 历史记录 —— 端到端 pytest 落地版。

把 `scripts/smoke_auth.py` 里逐条打印的断言固化成断言式用例，纳入 `pytest tests`
套件与回归门禁（对应 Spec §8 的 AC-01 ~ AC-13 及 §5.2 追加字段）。

`scripts/smoke_auth.py` 仍然保留：它是「人工一键冒烟」，打印逐条 PASS/FAIL，
便于现场演示与排障；本文件是同一批断言的 CI 形态，两者互补。

-----------------------------------------------------------------------------
【关键：与真实库 data/agriguard.db 隔离】
产品代码现已提供正式的覆盖入口：`AGRI_DB_PATH`（`app/db.py` 的 `DB_PATH_ENV`）。
该变量在 db 模块 **import 时读取一次**，故由 `tests/conftest.py` 在 import `app.*`
之前把它指向会话专属临时库。本文件因此**不再 monkeypatch 内部全局**，
只负责建 TestClient；隔离由 conftest 的正式入口统一保证。
（`AGRI_DB_PATH` 入口本身的回归见 `tests/test_db_path_env.py`。）
"""

import io
import sqlite3
import uuid
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app import constants
from app.main import app
from app.repositories import users as users_repo

ROOT = Path(__file__).resolve().parent.parent
DISPLAY_IMG = ROOT / "test_assets" / "supported_diseased" / "Tomato__Early_blight.jpg"
DEMO = {"username": "demo", "password": "demo1234"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    """进程内启动应用。库隔离由 tests/conftest.py 经 AGRI_DB_PATH 在 import 前完成。"""
    with TestClient(app) as c:
        yield c


def test_db_is_isolated_from_delivery_db():
    """护栏：确保测试确实跑在临时库上，绝不连交付库（防止隔离被误改而静默失效）。"""
    from app import db

    resolved = Path(db.DB_PATH).resolve()
    assert resolved != (ROOT / "data" / "agriguard.db").resolve(), (
        "测试连到了交付库 data/agriguard.db —— 隔离失效"
    )
    assert "agri_pytest_db_" in str(db.DB_PATH), (
        f"临时库路径不符合 conftest 约定：{db.DB_PATH}"
    )


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def _register(client, prefix="u"):
    """注册一个全新用户，返回 (username, token, headers)。"""
    uname = prefix + uuid.uuid4().hex[:8]
    r = client.post(
        "/api/v1/auth/register",
        json={"username": uname, "password": "pass12345"},
    )
    assert r.status_code == 200, f"注册失败 status={r.status_code} body={r.text}"
    token = r.json()["token"]
    return uname, token, {"Authorization": f"Bearer {token}"}


def _post_image(client, headers=None, filename="early_blight.jpg"):
    data = DISPLAY_IMG.read_bytes()
    return client.post(
        "/api/v1/predict",
        headers=headers or {},
        files={"file": (filename, io.BytesIO(data), "image/jpeg")},
    )


def test_display_asset_present():
    assert DISPLAY_IMG.is_file(), f"缺少展示用诊断图 {DISPLAY_IMG}"


# ---------------------------------------------------------------------------
# AC-03 / AC-01 / AC-02：登录、注册、重名
# ---------------------------------------------------------------------------
def test_demo_login_returns_token_and_user(client):
    r = client.post("/api/v1/auth/login", json=DEMO)
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["user"], "登录必须同时返回 token 与 user"
    assert body["user"]["username"] == "demo"


def test_duplicate_username_rejected_409(client):
    r = client.post("/api/v1/auth/register", json=DEMO)
    assert r.status_code == 409, f"重名注册应 409，实得 {r.status_code}"


def test_register_then_me(client):
    uname, _, auth = _register(client)
    r = client.get("/api/v1/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["user"]["username"] == uname


def test_register_validation_400(client):
    r = client.post("/api/v1/auth/register", json={"username": "x", "password": "pass12345"})
    assert r.status_code == 400, "用户名过短应 400"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "y" + uuid.uuid4().hex[:6], "password": "short"},
    )
    assert r.status_code == 400, "密码过短应 400"


def test_duplicate_username_data_layer_contract(client):
    """数据层：重名返回 None；**非用户名约束**的 IntegrityError 必须上抛。

    回归点：曾经把任意 IntegrityError 无条件吞成「用户名已被占用」，
    导致其它约束错误被误报为 409，掩盖真实故障。
    """
    assert users_repo.create_user("demo", "x", "h", "00") is None
    with pytest.raises(sqlite3.IntegrityError):
        # password_hash=None 触发 NOT NULL 约束（与用户名唯一约束无关）
        users_repo.create_user("nz_" + uuid.uuid4().hex[:8], "n", None, "00")


# ---------------------------------------------------------------------------
# AC-04：登录失败不区分「账号不存在」与「密码错误」
# ---------------------------------------------------------------------------
def test_login_failure_indistinguishable(client):
    uname, _, _ = _register(client)
    r_wrong_pw = client.post(
        "/api/v1/auth/login", json={"username": uname, "password": "wrongpass"}
    )
    r_no_user = client.post(
        "/api/v1/auth/login", json={"username": "no_such_user_zzz", "password": "anything"}
    )
    assert r_wrong_pw.status_code == 401
    assert r_no_user.status_code == 401
    # 状态码与响应体都必须一致（不泄露账号是否存在）
    assert r_wrong_pw.status_code == r_no_user.status_code
    assert r_wrong_pw.json() == r_no_user.json(), (
        f"两种失败响应体不一致，存在账号存在性泄露：\n{r_wrong_pw.text}\n{r_no_user.text}"
    )


# ---------------------------------------------------------------------------
# AC-05：未授权访问受保护接口
# ---------------------------------------------------------------------------
def test_unauthorized_access_401(client):
    assert client.get("/api/v1/history").status_code == 401, "无 token 应 401"
    assert (
        client.get("/api/v1/history", headers={"Authorization": "Bearer bad-token"}).status_code
        == 401
    ), "伪造 token 应 401"
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Token xyz"}).status_code == 401
    ), "非 Bearer 认证头应 401"


# ---------------------------------------------------------------------------
# AC-07 / AC-08：病例库索引与详情
# ---------------------------------------------------------------------------
def test_cases_index(client):
    r = client.get("/api/v1/cases")
    assert r.status_code == 200
    crops = r.json()["crops"]
    total = sum(int(c["count"]) for c in crops)
    assert len(crops) == 14, f"应覆盖 14 种作物，实得 {len(crops)}"
    assert total == 38, f"类别合计应为 38，实得 {total}"
    assert {c["crop_cn"] for c in crops} == set(constants.SUPPORTED_CROP_CN)


def test_case_detail_and_image(client):
    key = "Tomato___Early_blight"
    d = client.get(f"/api/v1/cases/{quote(key, safe='')}").json()
    assert d["crop_cn"] and d["disease_cn"], "详情缺少中英文名"
    assert d["summary"] and d["symptoms"] and d["prevention"], "详情缺少简介/症状/防治"
    assert d["image_url"], "详情未给出例图 URL"

    img = client.get(f"/api/v1/cases/image/{quote(key, safe='')}")
    assert img.status_code == 200
    assert img.headers.get("content-type", "").startswith("image/")

    # 含空格 / 括号的类别键也要能取到例图
    weird = "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"
    assert client.get(f"/api/v1/cases/image/{quote(weird, safe='')}").status_code == 200

    assert client.get("/api/v1/cases/Nope___Nope").status_code == 404


# ---------------------------------------------------------------------------
# AC-09 / §5.2：带 token 诊断自动入库
# ---------------------------------------------------------------------------
def test_predict_with_token_saves_history(client):
    _, _, auth = _register(client)
    r = _post_image(client, auth)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True, f"诊断应成功，reason={data.get('reason')}"
    assert data.get("history_id"), "带 token 诊断应自动入库并返回 history_id"
    assert data.get("class_key"), "§5.2 应下发 class_key"
    for k in ("ok", "detections", "ood_score", "prescription_source"):
        assert k in data, f"§5.2 既有字段被破坏，缺少 {k}"


def test_predict_without_token_not_saved(client):
    r = _post_image(client)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data.get("history_id") is None, "未登录不应入库"


def test_history_detail_and_thumbs(client):
    _, _, auth = _register(client)
    hid = _post_image(client, auth).json()["history_id"]

    d = client.get(f"/api/v1/history/{hid}", headers=auth)
    assert d.status_code == 200
    assert d.json()["item"]["prescription"] is not None, "历史详情缺处方结构"

    th = client.get(f"/api/v1/history/{hid}/thumb?kind=original", headers=auth)
    assert th.status_code == 200
    assert th.headers.get("content-type", "").startswith("image/")
    assert client.get(f"/api/v1/history/{hid}/thumb?kind=heatmap", headers=auth).status_code == 200


# ---------------------------------------------------------------------------
# AC-11：筛选 / 关键词 / 分页边界
# ---------------------------------------------------------------------------
def test_history_filter_and_keyword(client):
    _, _, auth = _register(client)
    _post_image(client, auth)  # 番茄 · 早疫病

    r = client.get("/api/v1/history?crop=%E7%95%AA%E8%8C%84", headers=auth).json()
    assert r["total"] >= 1 and all(i["crop_cn"] == "番茄" for i in r["items"])

    r = client.get("/api/v1/history?crop=tomato", headers=auth).json()
    assert r["total"] >= 1 and all(i["crop_cn"] == "番茄" for i in r["items"])

    assert client.get("/api/v1/history?q=%E6%97%A9%E7%96%AB", headers=auth).json()["total"] >= 1
    assert client.get("/api/v1/history?q=zzz_no_match_zzz", headers=auth).json()["total"] == 0
    # 无法识别的作物名 → 空结果（不得静默退化成「不过滤」）
    assert client.get("/api/v1/history?crop=zzz", headers=auth).json()["total"] == 0

    # 纯空白筛选必须等同「未提供筛选」
    base = client.get("/api/v1/history", headers=auth).json()["total"]
    for raw in ("%20", "%20%20"):
        got = client.get(f"/api/v1/history?crop={raw}", headers=auth).json()["total"]
        assert got == base, f"crop={raw} 纯空白应视为未筛选（base={base} got={got}）"
    assert client.get("/api/v1/history?q=%20", headers=auth).json()["total"] == base


def test_history_pagination_overflow_safe(client):
    _, _, auth = _register(client)
    r = client.get("/api/v1/history?limit=99999&offset=-5", headers=auth)
    assert r.status_code == 200, "分页参数越界应被安全收敛，而不是报错"


# ---------------------------------------------------------------------------
# AC-12 / AC-13：删除自己 / 越权隔离（404 不泄露存在性）
# ---------------------------------------------------------------------------
def test_delete_own_history(client):
    _, _, auth = _register(client)
    hid = _post_image(client, auth).json()["history_id"]
    assert client.delete(f"/api/v1/history/{hid}", headers=auth).status_code == 200
    assert client.get(f"/api/v1/history/{hid}", headers=auth).status_code == 404


def test_idor_foreign_equals_nonexistent(client):
    """越权读/删/取缩略图均 404，且响应体与「id 不存在」逐字节一致。"""
    _, _, auth_a = _register(client, prefix="a")
    _, _, auth_b = _register(client, prefix="b")
    hid = _post_image(client, auth_a).json()["history_id"]

    foreign_read = client.get(f"/api/v1/history/{hid}", headers=auth_b)
    foreign_del = client.delete(f"/api/v1/history/{hid}", headers=auth_b)
    foreign_thumb = client.get(f"/api/v1/history/{hid}/thumb", headers=auth_b)
    assert foreign_read.status_code == 404
    assert foreign_del.status_code == 404
    assert foreign_thumb.status_code == 404

    # 与「不存在的 id」对比：状态码与响应体必须完全一致，不能通过差异探测存在性
    ghost_read = client.get("/api/v1/history/99999999", headers=auth_b)
    ghost_del = client.delete("/api/v1/history/99999999", headers=auth_b)
    assert ghost_read.status_code == 404 and ghost_del.status_code == 404
    assert foreign_read.content == ghost_read.content, "越权读与不存在读的响应体必须逐字节一致"
    assert foreign_del.content == ghost_del.content, "越权删与不存在删的响应体必须逐字节一致"

    # 记录仍在，A 依旧可读（越权删除不能真的删掉别人的数据）
    assert client.get(f"/api/v1/history/{hid}", headers=auth_a).status_code == 200


# ---------------------------------------------------------------------------
# §5 可选端点：手动补录
# ---------------------------------------------------------------------------
def test_manual_create_history(client):
    _, _, auth = _register(client)
    r = client.post(
        "/api/v1/history",
        headers=auth,
        json={
            "class_key": "Tomato___Early_blight",
            "crop_cn": "番茄",
            "disease_cn": "早疫病",
            "confidence": 0.97,
            "severity_grade": "中",
            "prescription": {
                "disease": "番茄 · 早疫病",
                "severity": "中",
                "summary": "测试",
                "biological": "生物",
                "chemical": "化学",
                "tips": "提示",
            },
            "prescription_source": "template",
        },
    )
    assert r.status_code == 200
    mid = r.json()["id"]
    assert mid

    item = client.get(f"/api/v1/history/{mid}", headers=auth).json()["item"]
    assert item["prescription_source"] == "template"
    assert item["has_thumb"] is False, "手动补录无图片，缩略图应为空"
    assert client.delete(f"/api/v1/history/{mid}", headers=auth).status_code == 200


# ---------------------------------------------------------------------------
# AC-06：登出使令牌立即失效
# ---------------------------------------------------------------------------
def test_logout_invalidates_token_immediately(client):
    _, _, auth = _register(client)
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401


# ---------------------------------------------------------------------------
# 兼容性：旧别名 /predict
# ---------------------------------------------------------------------------
def test_legacy_predict_alias(client):
    data = DISPLAY_IMG.read_bytes()
    r = client.post("/predict", files={"file": ("d.jpg", io.BytesIO(data), "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json().get("history_id") is None, "旧别名未登录时同样不入库"
