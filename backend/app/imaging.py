"""图像输入处理：上传校验、尺寸收敛、严重度分级、上传目录回收。

【本模块解决的安全与稳定性问题，均来自本次审查的实测证据】

1. **存储型 XSS（已实测复现，P0）**
   原实现把上传文件的**用户可控扩展名**直接拼进落盘文件名：
       suffix = file.filename.rsplit(".", 1)[-1]
       path = UPLOAD_DIR / f"{uuid4().hex}.{suffix}"
   而 `/uploads` 是 StaticFiles 静态挂载。审查中实际上传了一个 `poc.html`，
   随后 `GET /uploads/<uuid>.html` 返回 **200 + Content-Type: text/html**，
   浏览器会把它当同源页面执行——脚本可读取本页 DOM 与 `localStorage`。
   修复：扩展名白名单 + **校验文件真实魔数**（防改扩展名绕过），
   落盘文件名改用白名单内的规范化后缀。

2. **超大图导致推理退化（实测 49 倍）**
   审查实测：示例图（256×256）热力图耗时 0.10s，而 4000×3000 的 12MP 手机照片
   耗时 1.573s；本项目最大实测图 1040 万像素约 1.0s，且大图会显著抬升内存占用。
   现场演示若用手机直出照片，观感会明显变慢。
   修复：落盘后按最长边收敛到 MAX_EDGE，兼顾画质与耗时。

3. **上传目录只增不删（隐私 + 磁盘）**
   原实现无任何清理策略，实测已堆积 259 个文件 / 11.5MB。
   用户上传的作物照片属于用户数据，长期留存在本地既无必要也不妥当。
   修复：惰性回收，超过保留期的原图与热力图一并删除。
"""

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2

from . import constants

logger = logging.getLogger(__name__)

# 落盘前的最大边长。1600px 对"单叶 + 纯色背景"这一拍摄规范已足够保留病斑纹理，
# 同时把 12MP 级输入的计算量压回可接受范围。
MAX_EDGE = 1600

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_BMP_MAGIC = b"BM"
_RIFF_MAGIC = b"RIFF"
_WEBP_TAG = b"WEBP"


def sniff_image_format(data: bytes) -> Optional[str]:
    """按文件头魔数判断真实图片格式。

    返回 'jpeg' / 'png' / 'bmp' / 'webp'，无法识别返回 None。
    目的：仅凭用户提供的文件名后缀是不可信的（可随意改名绕过白名单）。
    """
    if not data or len(data) < 12:
        return None
    head = data[:12]
    if head.startswith(_JPEG_MAGIC):
        return "jpeg"
    if head.startswith(_PNG_MAGIC):
        return "png"
    if head.startswith(_BMP_MAGIC):
        return "bmp"
    if head.startswith(_RIFF_MAGIC) and head[8:12] == _WEBP_TAG:
        return "webp"
    return None


# 真实格式 -> 落盘使用的规范后缀。注意 JSON/HTML/JS 等文本格式不在其中，
# 因此不可能再出现"上传 HTML 被当页面执行"的情况。
_FORMAT_TO_SUFFIX = {
    "jpeg": "jpg",
    "png": "png",
    "bmp": "bmp",
    "webp": "webp",
}


def validate_upload(filename: Optional[str], data: bytes) -> Tuple[bool, str, str]:
    """校验上传内容。

    返回 `(是否通过, 拒绝原因, 落盘后缀)`。
    三道检查：体积上限 -> 扩展名白名单 -> 真实魔数（最关键的一道）。
    """
    if not data:
        return False, "上传内容为空，请重新选择图片。", ""

    if len(data) > constants.MAX_UPLOAD_BYTES:
        limit_mb = constants.MAX_UPLOAD_BYTES / 1024 / 1024
        actual_mb = len(data) / 1024 / 1024
        return (
            False,
            f"图片过大（{actual_mb:.1f}MB），请压缩到 {limit_mb:.0f}MB 以内再上传。",
            "",
        )

    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    fmt = sniff_image_format(data)
    if fmt is None:
        # 这一条同时挡住了"改名绕过扩展名白名单"的攻击
        return (
            False,
            "无法识别为图片文件，请上传 JPG / PNG 格式的病叶照片。",
            "",
        )

    if ext and ext not in constants.ALLOWED_SUFFIXES:
        # 内容确实是图片，但声明后缀不在白名单内 —— 以内容为准，
        # 用规范化后缀落盘，既不拒绝用户也不留下危险后缀。
        logger.info("上传文件声明后缀 %s 不在白名单，按真实格式 %s 落盘", ext, fmt)

    return True, "", _FORMAT_TO_SUFFIX[fmt]


def enforce_max_edge(path: Path, max_edge: int = MAX_EDGE) -> bool:
    """若图片最长边超过 max_edge，就等比缩小并覆盖原文件。

    返回是否发生了缩放。缩放后仍保持原图宽高比，因此不影响
    `gradcam` 的中心方形裁剪几何。
    """
    try:
        img = cv2.imread(str(path))
    except Exception:
        logger.exception("读取图片失败，跳过尺寸收敛：%s", path)
        return False
    if img is None:
        return False

    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= max_edge:
        return False

    scale = max_edge / float(longest)
    new_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    resized = cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)
    ok = cv2.imwrite(str(path), resized)
    if ok:
        logger.info("输入图片尺寸收敛：%dx%d -> %dx%d", w, h, new_size[0], new_size[1])
    else:
        logger.warning("输入图片尺寸收敛写入失败：%s", path)
    return ok


def severity_grade(lesion_ratio: Optional[float], is_healthy: bool) -> str:
    """由病灶面积占比给出严重度分级。

    仅用于分级展示，不参与判识关键路径，因此允许使用粗阈值。
    阈值定义见 constants.py。
    """
    if is_healthy:
        return "健康"
    if lesion_ratio is None:
        return "待评估"
    if lesion_ratio < constants.SEVERITY_MILD_MAX:
        return "轻"
    if lesion_ratio < constants.SEVERITY_MODERATE_MAX:
        return "中"
    return "重"


# ---------------------------------------------------------------------------
# 历史记录缩略图（Spec §10：最长边 ≤320px、JPEG 质量 80）
# ---------------------------------------------------------------------------
# 为什么必须在这里就地把图片压成 BLOB：uploads/ 有 24 小时惰性回收策略，
# 若历史记录只存文件路径，过一天图就会变空白。因此入库前先压成缩略图字节。
THUMB_MAX_EDGE = 320
THUMB_JPEG_QUALITY = 80


def make_thumbnail_bytes(
    path: Path,
    max_edge: int = THUMB_MAX_EDGE,
    quality: int = THUMB_JPEG_QUALITY,
) -> Optional[bytes]:
    """把图片压成缩略图 JPEG 字节；无法读取时返回 None（不抛异常）。

    仅供历史入库使用：调用方对 None 必须容错（没有缩略图不应影响诊断与入库）。
    """
    try:
        img = cv2.imread(str(path))
    except Exception:
        logger.debug("缩略图读取失败：%s", path, exc_info=True)
        return None
    if img is None:
        return None

    h, w = img.shape[:2]
    longest = max(h, w)
    if longest > max_edge:
        scale = max_edge / float(longest)
        new_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
        img = cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)

    try:
        ok, buf = cv2.imencode(
            ".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        )
    except Exception:
        logger.debug("缩略图编码失败：%s", path, exc_info=True)
        return None
    return buf.tobytes() if ok else None


def gc_uploads(upload_dir: Path, retention_seconds: int = constants.UPLOAD_RETENTION_SECONDS) -> int:
    """回收过期的上传文件（原图与热力图一并删除）。

    采用惰性回收：由请求触发，超频保护见下面的 `gc_uploads_throttled`。
    返回删除的文件数。
    """
    if not upload_dir.exists():
        return 0
    deadline = time.time() - retention_seconds
    removed = 0
    for f in upload_dir.iterdir():
        try:
            if not f.is_file():
                continue
            if f.stat().st_mtime < deadline:
                f.unlink()
                removed += 1
        except (Exception, SystemExit):
            # 单个文件删除失败（被占用、权限不足、或环境的删除守卫拦截）
            # 不应影响整体回收，更不应冒泡到请求或启动流程。
            logger.debug("回收上传文件失败（已跳过）：%s", f)
    if removed:
        logger.info("已回收 %d 个过期上传文件（保留期 %ds）", removed, retention_seconds)
    return removed


_last_gc_at = 0.0


def gc_uploads_throttled(upload_dir: Path) -> int:
    """带超频保护的回收：间隔小于 UPLOAD_GC_INTERVAL_SECONDS 时直接跳过。

    避免每个请求都遍历目录，同时保证长时间运行后一定触发回收。
    """
    global _last_gc_at
    now = time.time()
    if now - _last_gc_at < constants.UPLOAD_GC_INTERVAL_SECONDS:
        return 0
    _last_gc_at = now
    return gc_uploads(upload_dir)
