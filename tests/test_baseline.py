"""端到端回归基线（pytest 版）。

相对 `scripts/verify_pipeline.py` 的改进，也正是当初「回归长期静默失败」的根因修复：
1. **不需要事先手动启动服务** —— 用 FastAPI TestClient 在进程内跑，天然适合 CI。
2. **阈值全部从接口读**，不硬编码，杜绝与 `constants.py` 形成双份真源。
3. **把拒识演示素材本身纳入回归**：`frontend/_demo_leaf_ood.jpg` 必须仍能落进
   OOD 拒识区。否则一旦该素材被替换或损坏，现场演示会当场失效却无人察觉。

运行方式（在项目根目录）：
    .venv\\Scripts\\python.exe -m pytest tests -v

⚠️ 判据与被测模型强绑定。**每次重训模型后，必须重新运行并按实测结果更新
下列断言与常量，同时同步 `backend/app/constants.py` 的标定注释。**
历史上正是因为重训后没做这一步，导致夹具失效、回归长期 4/5 却无人发现。
"""

import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

# ---------------------------------------------------------------------------
# 与当前部署权重（models/best.pt，v2）实测对应的锚点。
# 换模型后请重测并更新，勿凭感觉改。
# ---------------------------------------------------------------------------
SYNTHETIC_WARN_BAND = (0.25, 0.32)   # 白底/灰底合成绿椭圆落点区间
OOD_ASSET_MAX_SCORE = 0.25           # 拒识演示素材必须低于拒识阈值
NORMAL_ASSET_MIN_SCORE = 0.32        # 合规示例图必须高于警告阈值


@pytest.fixture(scope="module")
def client():
    """进程内启动应用（含启动钩子：建目录 + 模型预热）。"""
    with TestClient(app) as c:
        yield c


def _post(client, data: bytes, filename: str, content_type: str = "image/jpeg") -> dict:
    r = client.post(
        "/api/v1/predict",
        files={"file": (filename, io.BytesIO(data), content_type)},
    )
    assert r.status_code == 200, f"期望 200，实得 {r.status_code}"
    return r.json()


def _encode(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _solid_bg_ellipse(bg_bgr, size: int = 300) -> bytes:
    """纯色背景 + 绿色椭圆。背景色是控制 OOD 分数的旋钮（实测）：
    黑底约 0.22（拒识）/ 灰底约 0.27（警告）/ 白底约 0.30（警告）。"""
    img = np.full((size, size, 3), bg_bgr, np.uint8)
    cv2.ellipse(img, (size // 2, size // 2), (100, 60), 30, 0, 360, (34, 139, 34), -1)
    return _encode(img)


# ---------------------------------------------------------------------------
# 基础可用性
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_ready"] is True, "模型未就绪，后续用例无意义"


def test_origin_signature_headers(client):
    """原创指纹响应头必须存在（防抄袭取证与原创性举证依赖它）。"""
    h = client.get("/health").headers
    assert h.get("X-AgriGuard-Work") == "AGRI-GUARD"
    assert h.get("X-AgriGuard-Signature") == "HM-AG-2026-0920"


# ---------------------------------------------------------------------------
# 契约：阈值与作物清单只能来自后端（消除前后端双份真源）
# ---------------------------------------------------------------------------

def test_meta_contract(client):
    meta = client.get("/api/v1/meta").json()
    assert float(meta["ood_reject_threshold"]) < float(meta["ood_warn_threshold"])
    assert len(meta["supported_crops"]) >= 10
    assert meta["allowed_suffixes"], "上传后缀白名单不能为空"
    assert float(meta["max_upload_mb"]) > 0


def test_thresholds_echoed_in_predict_response(client):
    """每次 /predict 响应都要回传阈值，前端据此渲染，避免文案漂移。"""
    meta = client.get("/api/v1/meta").json()
    data = _post(client, (FRONTEND / "_demo_leaf_compliant.jpg").read_bytes(), "demo.jpg")
    assert float(data["ood_reject_threshold"]) == float(meta["ood_reject_threshold"])
    assert float(data["ood_warn_threshold"]) == float(meta["ood_warn_threshold"])


# ---------------------------------------------------------------------------
# 安全回归
# ---------------------------------------------------------------------------

def test_non_image_rejected(client):
    """伪装成图片的 HTML 必须被拒（曾实测可触发同源存储型 XSS）。"""
    poc = b"<html><body><script>alert(1)</script></body></html>"
    data = _post(client, poc, "poc.html", "text/html")
    assert data["ok"] is False
    assert "图片" in (data.get("reason") or "")


def test_renamed_non_image_rejected(client):
    """改扩展名绕过同样必须被拒（靠真实文件魔数校验）。"""
    poc = b"<html><body>x</body></html>"
    data = _post(client, poc, "evil.jpg", "image/jpeg")
    assert data["ok"] is False


def test_oversized_upload_rejected(client):
    """超过体积上限必须被拒，且不进入推理。"""
    big = b"\xff\xd8\xff" + b"\x00" * (13 * 1024 * 1024)
    data = _post(client, big, "big.jpg")
    assert data["ok"] is False
    assert "过大" in (data.get("reason") or "")


# ---------------------------------------------------------------------------
# 业务链路
# ---------------------------------------------------------------------------

def test_background_rejected(client):
    """纹理背景（开发早期的示例图）应被拍摄形式校验拦下。"""
    src = FRONTEND / "_demo_leaf.jpg"
    if not src.exists():
        pytest.skip("缺少纹理背景测试素材 frontend/_demo_leaf.jpg")
    data = _post(client, src.read_bytes(), "textured.jpg")
    assert data["ok"] is False
    assert "背景" in (data.get("reason") or "")


def test_synthetic_ood_band(client):
    """合成图应落在警告区：返回结果但明确提示仅供参考。"""
    data = _post(client, _solid_bg_ellipse((128, 128, 128)), "syn_gray.jpg")
    ood = data.get("ood_score")
    assert ood is not None, "未进入 OOD 判定，可能被前置校验拦截"
    lo, hi = SYNTHETIC_WARN_BAND
    assert lo <= float(ood) < hi, (
        f"合成图 ood={ood} 已跌出警告区 {SYNTHETIC_WARN_BAND}；"
        "若模型已更换，请重新标定本用例"
    )
    assert data.get("warning") is not None


def test_normal_recognition_full_chain(client):
    """合规示例图：识别 + 热力图 + 处方，三项都要产出。"""
    src = FRONTEND / "_demo_leaf_compliant.jpg"
    assert src.exists(), f"缺少合规示例图 {src}"
    data = _post(client, src.read_bytes(), "compliant.jpg")

    assert data["ok"] is True
    assert data["detections"], "未返回识别结果"
    assert float(data["ood_score"]) >= NORMAL_ASSET_MIN_SCORE
    assert data.get("warning") is None
    assert data.get("heatmap_url"), "未生成热力图"
    assert data.get("lesion_ratio") is not None, "未输出病灶占比（可解释性量化缺失）"
    assert data.get("severity_grade"), "未输出严重度分级"
    assert data.get("prescription") is not None
    assert data.get("prescription_source") in ("llm", "template"), (
        "处方来源必须如实标注（llm / template）"
    )
    assert data.get("latency_ms") is not None


def test_ood_demo_asset_still_rejects(client):
    """拒识演示素材必须仍落进拒识区。

    这条用例是「演示资产保护」：现场演示高度依赖它，
    若素材被替换/压缩/损坏而静默失效，演示会当场演不出来。
    """
    src = FRONTEND / "_demo_leaf_ood.jpg"
    assert src.exists(), f"缺少拒识演示素材 {src}（来源与授权见 docs/演示素材.md）"
    data = _post(client, src.read_bytes(), "_demo_leaf_ood.jpg")

    ood = data.get("ood_score")
    assert ood is not None, (
        f"该素材被前置校验拦截而非进入 OOD（leaf_ratio={data.get('leaf_ratio')}），"
        "请更换素材"
    )
    assert float(ood) < OOD_ASSET_MAX_SCORE, (
        f"拒识素材 ood={ood} 未低于拒识阈值 {OOD_ASSET_MAX_SCORE}，演示会失效"
    )
    assert data["ok"] is False
    assert "可识别范围" in (data.get("reason") or "")
    assert data.get("detections"), "拒识时仍应回传原始 top3 供人工参考"


def test_legacy_predict_alias(client):
    """旧路径 /predict 仍须兼容（现有脚本与外部调用依赖它）。"""
    src = FRONTEND / "_demo_leaf_compliant.jpg"
    r = client.post("/predict", files={"file": ("d.jpg", io.BytesIO(src.read_bytes()), "image/jpeg")})
    assert r.status_code == 200
    assert r.json().get("ok") is True
