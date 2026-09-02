"""端到端回归测试：验证 /predict 接口的前置校验 + OOD 双阈值 + 正常识别链路。

运行前请先启动后端服务：
    cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

然后执行：
    .venv/Scripts/python.exe scripts/verify_pipeline.py

退出码：0 表示全部通过，非 0 表示有失败。

测试用例与当前阈值对应关系（见 backend/app/detector.py）：
    - 拒识阈值 ood_reject_threshold = 0.25（低于此值 OOD 拒识，但附带模型 top3）
    - 警告阈值 ood_warn_threshold  = 0.32（0.25~0.32 返回结果但附「仅供参考」警告）
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import requests

ROOT = Path(__file__).parent.parent
BASE_URL = "http://127.0.0.1:8000"

RESULTS = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        RESULTS.append((name, True, ""))
        print(f"✅ {name}")
    else:
        RESULTS.append((name, False, detail))
        print(f"❌ {name}: {detail}")


def predict_from_bytes(data: bytes, filename: str) -> dict:
    return requests.post(
        f"{BASE_URL}/predict",
        files={"file": (filename, data, "image/jpeg")},
        timeout=60,
    ).json()


def make_green_ellipse(scale: float) -> bytes:
    """生成「纯白背景 + 绿色椭圆」合成图，用于触发 OOD 区间。

    scale 越大椭圆越大，ood_score 越高（实测）：
        scale=1.0 -> ood≈0.242（< 0.25，OOD 拒识）
        scale=1.4 -> ood≈0.259（0.25~0.32，警告区间）
    scale>=1.6 时椭圆贴边，前置校验会先拒绝，不再进入 OOD 检测。
    """
    img = np.full((300, 300, 3), 255, np.uint8)
    a, b = int(100 * scale), int(60 * scale)
    cv2.ellipse(img, (150, 150), (a, b), 30, 0, 360, (34, 139, 34), -1)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def main():
    # 1. health
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        check("health", r.status_code == 200, r.text)
    except Exception as e:
        check("health", False, str(e))

    # 2. 纹理背景 demo 应被前置校验拒绝
    try:
        with open(ROOT / "frontend" / "_demo_leaf.jpg", "rb") as f:
            data = predict_from_bytes(f.read(), "demo.jpg")
        check(
            "background_rejected",
            data.get("ok") is False and "背景" in data.get("reason", ""),
            f"ok={data.get('ok')}, reason={data.get('reason')}",
        )
    except Exception as e:
        check("background_rejected", False, str(e))

    # 3. 绿色椭圆（ood≈0.242）应被 OOD 拒识，且附带模型 top3（方案 B 特性）
    try:
        data = predict_from_bytes(make_green_ellipse(1.0), "green_ellipse.jpg")
        check(
            "ood_rejected",
            data.get("ok") is False
            and "可识别范围" in data.get("reason", "")
            and data.get("ood_score", 1.0) < 0.25
            and len(data.get("detections", [])) > 0,
            f"ok={data.get('ok')}, reason={data.get('reason')}, "
            f"ood_score={data.get('ood_score')}, detections={data.get('detections')}",
        )
    except Exception as e:
        check("ood_rejected", False, str(e))

    # 4. 合规 demo 应正常识别且无警告（ood≥0.32）
    try:
        with open(ROOT / "frontend" / "_demo_leaf_compliant.jpg", "rb") as f:
            data = predict_from_bytes(f.read(), "compliant.jpg")
        check(
            "normal_recognition",
            data.get("ok") is True
            and len(data.get("detections", [])) > 0
            and data.get("warning") is None
            and data.get("ood_score", 0) >= 0.32,
            f"ok={data.get('ok')}, detections={data.get('detections')}, "
            f"warning={data.get('warning')}, ood_score={data.get('ood_score')}",
        )
    except Exception as e:
        check("normal_recognition", False, str(e))

    # 5. 绿色椭圆（ood≈0.259）应进入警告区间（通过但带 warning）
    try:
        data = predict_from_bytes(make_green_ellipse(1.4), "green_ellipse_warn.jpg")
        check(
            "warning_zone",
            data.get("ok") is True
            and data.get("warning") is not None
            and "仅供参考" in data.get("warning", ""),
            f"ok={data.get('ok')}, warning={data.get('warning')}, ood_score={data.get('ood_score')}",
        )
    except Exception as e:
        check("warning_zone", False, str(e))

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{passed}/{total} checks passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
