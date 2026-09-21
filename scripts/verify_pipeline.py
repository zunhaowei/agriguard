"""端到端回归测试：验证 /predict 接口的前置校验 + OOD 双阈值 + 正常识别链路。

运行前请先启动后端服务：
    cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

然后执行：
    .venv/Scripts/python.exe scripts/verify_pipeline.py

可用环境变量 AGRI_BASE_URL 覆盖目标地址（默认 http://127.0.0.1:8000）。
退出码：0 表示全部通过，非 0 表示有失败。

阈值语义（真值取自每次响应体下发的 ood_reject_threshold / ood_warn_threshold，
本脚本不硬编码，避免与 constants.py 形成双份真源）：
    ood_score <  reject  -> 拒识（仍回传 top3 供人工参考）
    reject <= score < warn -> 通过但附「仅供参考」警告
    score >= warn        -> 正常识别

【夹具标定说明 · 2026-09-20 按部署权重 models/best.pt (v2) 实测重标定】
旧版本用「纯白底 + 绿色椭圆」当拒识夹具，并假设其 ood≈0.24（<0.25）。但用当前
部署权重实测，白底绿色合成图形反而落在**警告区**——因为「绿色 + 均匀形状」正是
「健康叶」类权重向量的高相似方向：
    green_ellipse scale=0.8 -> 0.3023 / 1.0 -> 0.3025 / 1.4 -> 0.3036
故夹具改为按「背景色」拉开与训练分布的距离，实测（各 300x300 合成 JPEG）：
    拒识区（<0.25）：黑底绿椭圆 0.2216、绿点阵 0.1977
    警告区（0.25~0.32）：灰底绿椭圆 0.2734
    正常区（>=0.32）：真实合规番茄叶（frontend/_demo_leaf_compliant.jpg）0.3691
阈值本身（0.25 / 0.32）保持不变：合规真实图 0.37 稳在正常区、val 同分布抽样
均值 0.51，均未被误杀；阈值下调只为放过受支持作物，与本次夹具问题无关。
若更换模型权重，必须重跑本脚本并按实测同步更新夹具、断言与本说明。
"""
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import requests

ROOT = Path(__file__).parent.parent
BASE_URL = os.getenv("AGRI_BASE_URL", "http://127.0.0.1:8000")

GREEN = (34, 139, 34)  # BGR 森林绿

RESULTS = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        RESULTS.append((name, True, ""))
        print(f"[PASS] {name}")
    else:
        RESULTS.append((name, False, detail))
        print(f"[FAIL] {name}: {detail}")


def predict_from_bytes(data: bytes, filename: str) -> dict:
    return requests.post(
        f"{BASE_URL}/predict",
        files={"file": (filename, data, "image/jpeg")},
        timeout=60,
    ).json()


def _encode(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok, "JPEG 编码失败"
    return buf.tobytes()


def make_solid_bg_ellipse(bg_bgr, leaf_bgr=GREEN, size: int = 300) -> bytes:
    """生成「纯色背景 + 绿色椭圆」合成图。

    背景色是控制 ood_score 的关键旋钮（实测见模块 docstring）：
        黑底 -> 约 0.22（拒识） / 灰底 -> 约 0.27（警告） / 白底 -> 约 0.30（警告）
    三种背景都满足前置校验（均匀背景 + 绿色像素占比 >= 8%），因此都能进入 OOD 判定。
    """
    img = np.full((size, size, 3), bg_bgr, np.uint8)
    cv2.ellipse(img, (size // 2, size // 2), (100, 60), 30, 0, 360, leaf_bgr, -1)
    return _encode(img)


def main():
    # 1. health
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        check("health", r.status_code == 200, r.text)
    except Exception as e:
        check("health", False, str(e))
        _summary()
        return

    # 2. 非叶片内容应被前置校验拒绝
    #    说明：原先这里用「纹理背景示例图」做用例，但 2026-09-20 前置校验重标定后，
    #    背景判据改为「只在真背景像素上评估」，那张图的背景不再被视为不合规
    #    （它带轻微纹理但主色集中）。改用无绿色像素的纯灰块，作为稳定的不变式用例。
    try:
        img = np.full((300, 300, 3), 128, np.uint8)
        ok_enc, buf = cv2.imencode(".jpg", img)
        assert ok_enc
        data = predict_from_bytes(buf.tobytes(), "gray_block.jpg")
        check(
            "non_leaf_rejected",
            data.get("ok") is False and "未检测到叶片" in (data.get("reason") or ""),
            f"ok={data.get('ok')}, reason={data.get('reason')}",
        )
    except Exception as e:
        check("non_leaf_rejected", False, str(e))

    # 3. 黑底椭圆（ood≈0.22）应被 OOD 拒识，且附带模型 top3（方案 B 特性）
    try:
        data = predict_from_bytes(make_solid_bg_ellipse((0, 0, 0)), "ood_black.jpg")
        rej = data.get("ood_reject_threshold", 0.25)
        ood = data.get("ood_score")
        check(
            "ood_rejected",
            data.get("ok") is False
            and "可识别范围" in (data.get("reason") or "")
            and ood is not None
            and ood < rej
            and len(data.get("detections") or []) > 0,
            f"ok={data.get('ok')}, reason={data.get('reason')}, "
            f"ood_score={ood}, reject_threshold={rej}, "
            f"detections={data.get('detections')}",
        )
    except Exception as e:
        check("ood_rejected", False, str(e))

    # 4. 合规 demo 应正常识别且无警告（ood>=warn）
    try:
        with open(ROOT / "frontend" / "_demo_leaf_compliant.jpg", "rb") as f:
            data = predict_from_bytes(f.read(), "compliant.jpg")
        warn = data.get("ood_warn_threshold", 0.32)
        ood = data.get("ood_score") or 0
        check(
            "normal_recognition",
            data.get("ok") is True
            and len(data.get("detections") or []) > 0
            and data.get("warning") is None
            and ood >= warn,
            f"ok={data.get('ok')}, detections={data.get('detections')}, "
            f"warning={data.get('warning')}, ood_score={data.get('ood_score')}, "
            f"warn_threshold={warn}",
        )
    except Exception as e:
        check("normal_recognition", False, str(e))

    # 5. 灰底椭圆（ood≈0.27）应进入警告区间（通过但带 warning）
    try:
        data = predict_from_bytes(make_solid_bg_ellipse((128, 128, 128)), "ood_gray.jpg")
        check(
            "warning_zone",
            data.get("ok") is True
            and data.get("warning") is not None
            and "仅供参考" in (data.get("warning") or ""),
            f"ok={data.get('ok')}, warning={data.get('warning')}, "
            f"ood_score={data.get('ood_score')}",
        )
    except Exception as e:
        check("warning_zone", False, str(e))

    _summary()


def _summary():
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} checks passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
