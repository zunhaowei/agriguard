"""诊断主流程（推理编排）。

【本文件系从 `main.py` 纯搬迁而来，行为逐字节保持一致】
搬迁原因：功能扩展后 `main.py` 超出团队「单文件 ≤ 300 行」指引。按「入口只装配」
的分层规范，把「上传校验 → 尺寸收敛 → 前置校验 → 检测 → 热力图 → 处方 → 可选入库」
整段迁入服务层，入口只保留薄壳路由。**逻辑一字未改**，仅更换了所在文件。

【随迁的编排层修正说明（原文保留）】

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
   修复：用 `model_lock` 把「推理 + 热力图」这段临界区串行化；
   注意大模型调用（纯网络 I/O）**放在锁外**，避免一次慢调用拖住所有推理。

3. **上传无边界（安全，含已实测复现的存储型 XSS）**
   修复：体积上限 + 扩展名白名单 + 真实魔数校验 + 惰性回收（见 imaging.py）。
"""

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile

from .. import constants, imaging
from ..config import UPLOAD_DIR
from ..detector import Detector
from ..gradcam import generate_cam
from ..precheck import check_leaf_and_background
from ..prescriber import Prescriber
from ..schemas import PredictResponse
from . import history as history_service

# 日志通道名保持 "agriguard" 不变，搬迁后日志输出与原先完全一致。
logger = logging.getLogger("agriguard")

detector = Detector()
prescriber = Prescriber()

# 推理临界区锁：串行化「模型推理 + 热力图生成」。
# 为什么需要：gradcam 会临时切换共享模型的 requires_grad 并注册 hook，
# 两个并发调用会交叉触发彼此的 hook，属于全局状态竞争，无法靠局部状态消除。
# 为什么锁粒度是粗的：本项目运行在单张 GPU 上，推理本就是串行资源，
# 把过去"靠事件循环被阻塞意外串行化"变成显式串行，是诚实而非降级。
# 大模型处方调用必须放在锁外（纯网络 I/O，不碰模型）。
model_lock = threading.Lock()


def prime_forward() -> None:
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


def run_prediction(file: UploadFile, user: Optional[dict] = None) -> PredictResponse:
    """核心诊断流程（同步，由线程池执行）。

    注意：本函数不读取 `detector` 之外的全局可变状态；
    `detect` 与 `generate_cam` 由调用方持锁串行执行。

    `user` 为可选登录用户（Spec §5.1）：非 None 时在诊断成功后自动落一条历史。
    未登录传 None —— 只诊断、不入库、不报错。
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
    class_key: Optional[str] = None
    heat_path: Optional[Path] = None
    try:
        with model_lock:
            detections, ood_score, is_ood, is_warning = detector.detect(str(path))

            # 命中的类别键（PlantVillage 原始类名），供前端跳转病例库。
            # 仅读取权重自带的 names 映射，不额外触碰推理状态。
            if detections and detections[0].class_id is not None:
                class_key = detector.class_key_for(detections[0].class_id)

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
                    heat_path = None
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
            class_key=class_key,
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

    response = PredictResponse(
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
        class_key=class_key,
        **_runtime_meta(),
    )

    # ---- 7. 可选入库：仅登录用户、且诊断成功时写一条历史（含缩略图）----
    # 入库失败绝不冒泡到诊断链路（诊断结果才是用户要的东西）。
    if user is not None:
        try:
            response.history_id = history_service.save_from_response(
                int(user["id"]), response, class_key, path, heat_path
            )
        except (Exception, SystemExit):
            logger.exception("诊断历史入库失败（不影响本次诊断结果）")
    return response


def _runtime_meta() -> dict:
    info = detector.model_info()
    return {
        "model_name": info.get("model_name"),
        "model_weight_mb": info.get("model_weight_mb"),
        "device": info.get("device"),
    }


def gc_uploads() -> None:
    """回收过期上传文件。任何失败都必须被吞掉 —— 这是请求收尾的清理动作，
    绝不允许它把请求或进程搞挂（含某些环境删除守卫抛出的基类异常）。"""
    try:
        imaging.gc_uploads_throttled(UPLOAD_DIR)
    except (Exception, SystemExit):
        logger.debug("上传目录回收失败（忽略）", exc_info=True)
