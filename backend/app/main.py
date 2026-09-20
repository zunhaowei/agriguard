"""禾目 AgriGuard —— 推理服务入口。

禾目 AgriGuard · 作物病虫害智能诊断与精准处方系统
原创作品标识 AGRI-GUARD/v1.0 · 2026-09-20
本文件由禾目团队独立设计与实现。作品指纹见 constants.ORIGIN_SIGNATURE。

【本次审查修正的编排层问题】

1. **事件循环被堵死（并发缺陷）**
   原先 `/predict` 声明为 `async def`，但函数体内全程同步阻塞
   （落盘、OpenCV、YOLO 推理、requests 调大模型）。这会让 uvicorn 的
   事件循环在单次请求期间完全停摆——连 `/health` 和静态文件都无响应，
   大模型超时最坏 30 秒内整个服务假死。
   修复：改为 `def`（同步），FastAPI 会自动把它们派发到 anyio 工作线程池，
   事件循环立刻解放。

2. **单例共享可变状态的竞态（并发缺陷）**
   改为线程池后会真并发，而 `detector` 与 `gradcam` 都在操作共享模型状态
   （gradcam 会临时切换 `requires_grad` 并向共享模型注册 hook）。
   修复：用 `_model_lock` 把「推理 + 热力图」这段临界区串行化；
   注意大模型调用（纯网络 I/O）**放在锁外**，避免一次慢调用拖住所有推理。

3. **异常处理缺失（正确性）**
   原实现没有全局异常处理器，任何未捕获异常都会返回 FastAPI 默认的
   纯文本 500。前端 `r.json()` 会解析失败，用户只看到"诊断失败"而无从判断。
   修复：统一异常处理器，返回与正常响应同构的 JSON。

4. **上传无边界（安全，含已实测复现的存储型 XSS）**
   原先扩展名取自用户文件名、无体积上限、无类型校验、落盘后永不清理，
   实测可上传 .html 并由 `/uploads` 以 text/html 返回执行。
   修复：体积上限 + 扩展名白名单 + 真实魔数校验 + 惰性回收（见 imaging.py）。

5. **前后端阈值双份真源**
   阈值经 `/api/v1/meta` 与响应体统一下发，前端不再硬编码。
"""

import logging
import threading
import time
import uuid
from typing import Optional, Tuple

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import constants, imaging
from .config import FRONTEND_DIR, LLM_ENABLED, UPLOAD_DIR, ensure_dirs, resolve_model_path
from .constants import (
    ORIGIN_SIGNATURE,
    WORK_ID,
    WORK_NAME,
    WORK_TAGLINE,
    WORK_VERSION,
)
from .detector import Detector
from .gradcam import generate_cam
from .precheck import check_leaf_and_background
from .prescriber import Prescriber
from .schemas import HealthResponse, MetaResponse, PredictResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("agriguard")

app = FastAPI(
    title=f"{WORK_NAME} API",
    description=WORK_TAGLINE,
    version=WORK_VERSION,
)

# CORS 收敛说明：原为 allow_origins=["*"] + allow_methods=["*"] + allow_headers=["*"]，
# 等价于允许任意站点从浏览器读取本地推理服务的结果。本作品是**本机演示型**应用，
# 前端与后端同源（静态文件由本服务托管），因此跨源访问没有必要。
# 这里只保留本机开发/预览可能用到的来源，不再使用通配符。
_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5500",  # VS Code Live Server 预览
    "http://localhost:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

detector = Detector()
prescriber = Prescriber()

# 推理临界区锁：串行化「模型推理 + 热力图生成」。
# 为什么需要：gradcam 会临时切换共享模型的 requires_grad 并注册 hook，
# 两个并发调用会交叉触发彼此的 hook，属于全局状态竞争，无法靠局部状态消除。
# 为什么锁粒度是粗的：本项目运行在单张 GPU 上，推理本就是串行资源，
# 把过去"靠事件循环被阻塞意外串行化"变成显式串行，是诚实而非降级。
# 大模型处方调用必须放在锁外（纯网络 I/O，不碰模型）。
_model_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 中间件：作品指纹响应头（防抄袭取证 + 原创标识）
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_origin_signature(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-AgriGuard-Work"] = WORK_ID
    response.headers["X-AgriGuard-Version"] = WORK_VERSION
    response.headers["X-AgriGuard-Signature"] = ORIGIN_SIGNATURE
    return response


# ---------------------------------------------------------------------------
# 异常兜底：保证任何失败都返回与正常响应同构的 JSON
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=200,  # 业务层用 ok=false 表达失败，避免前端 r.json() 解析失败
        content=PredictResponse(
            ok=False,
            reason="服务内部异常，请重试。若持续出现请联系维护者查看后端日志。",
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# 启动钩子：建目录 + 预加载模型（消除现场演示的首次请求延迟）
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()
    imaging.gc_uploads_throttled(UPLOAD_DIR)

    t0 = time.perf_counter()
    try:
        path = resolve_model_path()
    except FileNotFoundError:
        logger.error("启动检查失败：未找到可用模型权重，服务将以不可用状态运行。")
        return

    # 预加载：原先模型是惰性的，首次 /predict 才加载。实测冷启动到首次返回
    # 约 6.7 秒暖机后 0.10 秒 —— 现场演示若第一次点击就等 6.7 秒，观感很差。
    # 故在启动阶段完成加载与一次前向，把延迟挪到无人观察的启动期。
    try:
        with _model_lock:
            detector.load()
            _prime_forward()
        logger.info(
            "模型预热完成，耗时 %.2fs | 权重=%s | %s",
            time.perf_counter() - t0,
            path.name,
            detector.model_info(),
        )
    except (Exception, SystemExit):
        # 预热失败不能阻止服务启动：宁可首次请求慢一点，也不能打不开页面。
        logger.exception("模型预热失败，服务仍会启动，但首次请求会较慢")


def _prime_forward() -> None:
    """用一张合成的合规图跑一次完整前向，预热 CUDA 与算子。"""
    import numpy as np
    import cv2

    warm_path = UPLOAD_DIR / f"_warmup_{uuid.uuid4().hex[:8]}.jpg"
    try:
        # 生成"白底 + 中央绿叶"的合成图，能通过前置校验
        canvas = np.full((320, 320, 3), 240, np.uint8)
        cv2.ellipse(canvas, (160, 160), (110, 90), 0, 0, 360, (60, 150, 70), -1)
        cv2.imwrite(str(warm_path), canvas)
        detector.detect(str(warm_path))
    except Exception:
        logger.debug("预热前向失败（不影响服务）", exc_info=True)
    finally:
        try:
            warm_path.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 静态资源
# ---------------------------------------------------------------------------
# ⚠️ 顺序关键：StaticFiles 在 mount 时会立刻检查目录是否存在，
# 目录缺失会直接抛 RuntimeError 让**整个应用无法启动**（实测确认）。
# 而原先建目录的动作放在 startup 钩子里 —— 钩子在 mount 之后才执行，
# 所以 uploads/ 一旦缺失（例如被清理、或全新克隆的仓库里没有该目录），
# 服务就连启动都做不到。因此在 mount 之前先确保目录存在。
# config.ensure_dirs() 是幂等的，startup 钩子里再调一次也无副作用。
ensure_dirs()

# 安全说明：仅挂载 frontend/ 目录（不含 .env 等敏感文件）。
# /uploads 只可能包含经过 imaging.validate_upload 白名单与魔数校验的位图，
# 因此不会再出现"上传 HTML 被当页面执行"的同源存储型 XSS。
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ---------------------------------------------------------------------------
# 基础端点
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", model_ready=detector.is_loaded)


@app.get("/api/v1/meta", response_model=MetaResponse)
def meta():
    """向前端下发业务常量真值，消除前后端各存一份的漂移风险。"""
    info = detector.model_info()
    return MetaResponse(
        supported_crops=list(constants.SUPPORTED_CROP_CN),
        ood_reject_threshold=constants.OOD_REJECT_THRESHOLD,
        ood_warn_threshold=constants.OOD_WARN_THRESHOLD,
        allowed_suffixes=list(constants.ALLOWED_SUFFIXES),
        model_name=info.get("model_name"),
        model_weight_mb=info.get("model_weight_mb"),
        device=info.get("device"),
        llm_enabled=LLM_ENABLED,
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def _read_limited(fp, limit: int) -> Tuple[Optional[bytes], int]:
    """分块读取上传内容，超过上限立即停止，避免把超大文件整个读进内存。"""
    chunks = []
    total = 0
    while True:
        chunk = fp.read(256 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            return None, total
        chunks.append(chunk)
    return b"".join(chunks), total


def _reject(reason: str, info: Optional[dict] = None, **extra) -> PredictResponse:
    """构造拒绝响应，统一带上阈值真值与作品标识。"""
    info = info or {}
    return PredictResponse(
        ok=False,
        reason=reason,
        leaf_ratio=info.get("leaf_ratio"),
        background_std=info.get("background_std"),
        background_dominant_ratio=info.get("background_dominant_ratio"),
        ood_reject_threshold=detector.ood_reject_threshold,
        ood_warn_threshold=detector.ood_warn_threshold,
        **extra,
    )


def _run_predict(file: UploadFile) -> PredictResponse:
    """核心诊断流程（同步，由线程池执行）。

    注意：本函数不读取 `detector` 之外的全局可变状态；
    `detect` 与 `generate_cam` 由调用方持锁串行执行。
    """
    t_start = time.perf_counter()

    # ---- 1. 读取与校验上传内容 ----
    raw, total = _read_limited(file.file, constants.MAX_UPLOAD_BYTES)
    if raw is None:
        return _reject(
            f"图片过大（超过 {constants.MAX_UPLOAD_BYTES / 1024 / 1024:.0f}MB），"
            "请压缩后重新上传。"
        )

    ok, reason, suffix = imaging.validate_upload(file.filename, raw)
    if not ok:
        return _reject(reason)

    path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{suffix}"
    try:
        with path.open("wb") as f:
            f.write(raw)
    except OSError:
        logger.exception("上传文件落盘失败：%s", path)
        return _reject("图片保存失败，请重试。")

    # ---- 2. 输入尺寸收敛（大图会显著拖慢热力图，实测 12MP 慢约 15 倍）----
    imaging.enforce_max_edge(path)

    # ---- 3. 拍摄形式前置校验 ----
    passed, pre_reason, info = check_leaf_and_background(str(path))
    if not passed:
        return _reject(pre_reason, info)

    # ---- 4. 模型推理（临界区，持锁）----
    try:
        with _model_lock:
            detections, ood_score, is_ood, is_warning = detector.detect(str(path))

            heatmap_url: Optional[str] = None
            lesion_ratio: Optional[float] = None
            cam_stats: dict = {}

            # 分布外拒识：图片通过了拍摄形式校验，但特征与训练分布差异过大。
            # 常见原因：训练集外物种、严重域偏移（田间实景 / 复杂光照 / 非实验室拍摄）。
            # 方案 B：即便拒识，也把模型原始 top3 一并返回，让用户看到"模型自认为是什么"，
            # 便于人工判断，而不是被一刀切拒绝。
            if not is_ood and detections and detections[0].class_id is not None:
                heat_path = UPLOAD_DIR / f"{path.stem}_heatmap.jpg"
                out, cam_stats = generate_cam(
                    detector.model, str(path), detections[0].class_id, str(heat_path)
                )
                if out:
                    heatmap_url = f"/uploads/{heat_path.name}"
                    lesion_ratio = cam_stats.get("lesion_ratio")
                else:
                    logger.warning("热力图未生成，本次响应将不含病灶定位图")
    except Exception:
        logger.exception("推理阶段异常")
        return _reject("识别过程出现异常，请重试。")

    # ---- 5. 分布外拒识 ----
    if is_ood:
        return _reject(
            "模型对当前图片不够确信，可能不在可识别范围内。"
            f"请确认叶片属于支持的作物（{constants.SUPPORTED_CROP_TEXT}），"
            "并在纯色背景下重新拍摄。",
            info,
            ood_score=ood_score,
            detections=detections,
            latency_ms=round((time.perf_counter() - t_start) * 1000, 1),
            **_runtime_meta(),
        )

    warning = None
    if is_warning:
        warning = (
            f"分布相似度偏低（{ood_score:.2f}），识别结果仅供参考，"
            "建议重新拍摄更清晰的纯色背景叶片图。"
        )

    # ---- 6. 处方生成（纯网络 I/O，必须在锁外，避免拖住其它请求的推理）----
    is_healthy = bool(detections) and "健康" in detections[0].name
    grade = imaging.severity_grade(lesion_ratio, is_healthy)
    try:
        prescription, source = prescriber.generate(detections, grade)
    except Exception:
        logger.exception("处方生成异常，返回空处方")
        prescription, source = None, None

    return PredictResponse(
        detections=detections,
        prescription=prescription,
        prescription_source=source,
        heatmap_url=heatmap_url,
        lesion_ratio=lesion_ratio,
        severity_grade=grade,
        ood_score=ood_score,
        ood_reject_threshold=detector.ood_reject_threshold,
        ood_warn_threshold=detector.ood_warn_threshold,
        warning=warning,
        leaf_ratio=info.get("leaf_ratio"),
        background_std=info.get("background_std"),
        background_dominant_ratio=info.get("background_dominant_ratio"),
        latency_ms=round((time.perf_counter() - t_start) * 1000, 1),
        **_runtime_meta(),
    )


def _runtime_meta() -> dict:
    info = detector.model_info()
    return {
        "model_name": info.get("model_name"),
        "model_weight_mb": info.get("model_weight_mb"),
        "device": info.get("device"),
    }


def _gc() -> None:
    """回收过期上传文件。任何失败都必须被吞掉 —— 这是请求收尾的清理动作，
    绝不允许它把请求或进程搞挂（含某些环境删除守卫抛出的基类异常）。"""
    try:
        imaging.gc_uploads_throttled(UPLOAD_DIR)
    except (Exception, SystemExit):
        logger.debug("上传目录回收失败（忽略）", exc_info=True)


# 注意：这里刻意使用 `def` 而不是 `async def`。
# FastAPI 会把同步端点派发到工作线程池执行，从而不阻塞事件循环。
# 若改回 async，函数体内的同步阻塞调用会让整个服务在单次请求期间无响应。
@app.post("/api/v1/predict", response_model=PredictResponse)
def predict_v1(file: UploadFile = File(...)):
    try:
        return _run_predict(file)
    finally:
        _gc()


# 旧路径别名：保持向后兼容（现有前端与脚本仍在使用 /predict）。
# 新代码请使用 /api/v1/predict。
@app.post("/predict", response_model=PredictResponse, include_in_schema=False)
def predict_legacy(file: UploadFile = File(...)):
    try:
        return _run_predict(file)
    finally:
        _gc()
