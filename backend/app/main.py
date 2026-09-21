"""禾目 AgriGuard —— 推理服务入口（只做装配）。

禾目 AgriGuard · 作物病虫害智能诊断与精准处方系统
原创作品标识 AGRI-GUARD/v1.0 · 2026-09-20
本文件由禾目团队独立设计与实现。作品指纹见 constants.ORIGIN_SIGNATURE。

【本文件的职责边界】
入口只做装配：建应用、挂中间件、挂静态资源、注册异常处理、include 路由、启动预热。
**不含任何业务逻辑**。具体分工：

- 诊断主流程（上传校验 → 尺寸收敛 → 前置校验 → 检测 → 热力图 → 处方 → 可选入库）
  → `services/prediction.py`（原在本文件内，因超出单文件行数指引而整段迁出，逻辑未改）
- 异常兜底 → `errors.py`
- 认证 / 病例库 / 历史记录 → `routers/*` → `services/*` → `repositories/*`

【历史决策（仍生效）】
- `/predict` 与 `/api/v1/predict` 都是 `def` 而非 `async def`：体内是同步阻塞调用
  （落盘、OpenCV、YOLO、requests），声明为 async 会让事件循环在单次请求期间
  完全停摆。用 `def` 后由 FastAPI 派发到工作线程池，事件循环立刻解放。
- `/api/v1/meta` 与响应体统一下发阈值真值，消除前后端各存一份的漂移风险。
- 上传校验（体积 / 后缀白名单 / 真实魔数 / 惰性回收）见 `imaging.py`。
"""

import logging
import time
from typing import Optional

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
from .db import DB_PATH, init_db
from .errors import register_error_handlers
from .routers import auth as auth_routes
from .routers import cases as cases_routes
from .routers import history as history_routes
from .routers.deps import optional_user
from .schemas import HealthResponse, MetaResponse, PredictResponse
from .services import accounts as accounts_service
from .services.prediction import (
    detector,
    gc_uploads,
    model_lock,
    prime_forward,
    run_prediction,
)

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
    # 功能扩展新增：历史记录需要 DELETE，认证需要携带 Authorization 头。
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


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
# 异常兜底：保证任何失败都返回与正常响应同构的 JSON（实现见 errors.py）
# ---------------------------------------------------------------------------
register_error_handlers(app)


# ---------------------------------------------------------------------------
# 启动钩子：建目录 + 建库 + 预加载模型（消除现场演示的首次请求延迟）
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()
    imaging.gc_uploads_throttled(UPLOAD_DIR)

    # 数据库：幂等建表 + 播种演示账号。属"可用性增强"而非"启动前置条件"，
    # 故失败只记录日志，核心诊断链路不受影响（与"辅助动作绝不阻断启动"红线一致）。
    try:
        init_db()
        accounts_service.ensure_demo_user()
        logger.info("数据库就绪：%s", DB_PATH)
    except (Exception, SystemExit):
        logger.exception("数据库初始化失败，账号与历史记录功能将不可用（诊断功能不受影响）")

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
        with model_lock:
            detector.load()
            prime_forward()
        logger.info(
            "模型预热完成，耗时 %.2fs | 权重=%s | %s",
            time.perf_counter() - t0,
            path.name,
            detector.model_info(),
        )
    except (Exception, SystemExit):
        # 预热失败不能阻止服务启动：宁可首次请求慢一点，也不能打不开页面。
        logger.exception("模型预热失败，服务仍会启动，但首次请求会较慢")


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
# 功能扩展路由（认证 / 病例库 / 历史记录）
# ---------------------------------------------------------------------------
# 业务实现全部分层落在 routers -> services -> repositories，入口只做装配。
app.include_router(auth_routes.router)
app.include_router(cases_routes.router)
app.include_router(history_routes.router)


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
# 诊断端点（薄壳：解析请求 -> 调服务 -> 返回响应）
# ---------------------------------------------------------------------------
# 注意：这里刻意使用 `def` 而不是 `async def`。
# FastAPI 会把同步端点派发到工作线程池执行，从而不阻塞事件循环。
# 若改回 async，函数体内的同步阻塞调用会让整个服务在单次请求期间无响应。
#
# `Authorization` 头是**可选**的（Spec §5.1）：
#   带有效令牌 -> 诊断成功后自动写一条历史（响应额外给出 history_id / class_key）
#   不带/令牌无效 -> 照常诊断，只是不入库、不报错（核心功能不设门槛）
@app.post("/api/v1/predict", response_model=PredictResponse)
def predict_v1(
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(optional_user),
):
    try:
        return run_prediction(file, user)
    finally:
        gc_uploads()


# 旧路径别名：保持向后兼容（现有前端与脚本仍在使用 /predict）。
# 新代码请使用 /api/v1/predict。它与新路径共享同一实现与同等的可选认证行为。
@app.post("/predict", response_model=PredictResponse, include_in_schema=False)
def predict_legacy(
    file: UploadFile = File(...),
    user: Optional[dict] = Depends(optional_user),
):
    try:
        return run_prediction(file, user)
    finally:
        gc_uploads()
