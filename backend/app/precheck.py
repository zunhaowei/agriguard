"""识别前的图像前置校验。

目标：确保输入照片满足「单叶 + 纯色背景」的拍摄条件，
与训练数据（PlantVillage 实验室摆拍）的分布对齐，从而显著提升识别准确率。
校验不通过时直接拒绝识别，避免给出不可靠的病害结果。
"""
from typing import Tuple

import cv2
import numpy as np

# ----------------- 可调阈值 -----------------
LEAF_MIN_RATIO = 0.08          # 绿色/黄绿色像素占比下限（判断“是叶片”）
BACKGROUND_BAND = 0.08         # 边缘采样带比例（四边各取 8%）

# 背景判定使用「标准差 + 主导色占比」双指标：
# 1) 理想纯色：标准差很低；
# 2) 纯色但带轻微阴影/褶皱：标准差略高，但 85% 以上像素仍集中在背景主色附近。
BACKGROUND_MAX_STD = 25.0            # 严格标准差上限（白/灰/单色背景通常 < 15）
BACKGROUND_MAX_STD_LOOSE = 55.0      # 宽松标准差上限（允许轻微阴影/褶皱）
BACKGROUND_MAX_DISTANCE = 45.0       # 与背景主色的 BGR 欧氏距离阈值
BACKGROUND_DOMINANT_RATIO = 0.85     # 主色附近像素占比下限

MIN_IMG_PX = 64                        # 最小图片尺寸

# HSV 颜色范围：绿色 + 黄绿色（覆盖健康叶与多数病叶）
_HSV_LOWER = np.array([25, 40, 40])
_HSV_UPPER = np.array([100, 255, 255])


def check_leaf_and_background(image_path: str) -> Tuple[bool, str, dict]:
    """校验「必须是叶片」且「背景为纯色」两个条件。

    返回 (ok, reason, info)。
    ok=True 表示通过，reason 为空字符串；
    ok=False 时 reason 为面向用户的拒绝原因，info 包含具体指标。
    """
    img = cv2.imread(image_path)
    if img is None:
        return False, "无法读取图片，请重新上传。", {}

    h, w = img.shape[:2]
    if h < MIN_IMG_PX or w < MIN_IMG_PX:
        return False, "图片尺寸过小，请上传清晰照片。", {}

    leaf_ratio = _leaf_ratio(img)
    bg_std, bg_dominant = _background_uniformity(img)
    bg_ok = _is_uniform_background(bg_std, bg_dominant)

    info = {
        "leaf_ratio": round(leaf_ratio, 4),
        "background_std": round(bg_std, 2),
        "background_dominant_ratio": round(bg_dominant, 4),
    }

    if leaf_ratio >= LEAF_MIN_RATIO and bg_ok:
        return True, "", info

    if leaf_ratio < LEAF_MIN_RATIO and not bg_ok:
        return (
            False,
            "未检测到叶片，且背景不是纯色。请拍摄单片叶片，并平铺在纯色背景（如白纸/灰布）上再上传。",
            info,
        )
    if leaf_ratio < LEAF_MIN_RATIO:
        return (
            False,
            "未检测到叶片，请确保画面主体为作物叶片，并重新拍摄。",
            info,
        )
    return (
        False,
        "背景不是纯色，请将叶片平铺在纯色背景（如白纸/灰布）上再拍摄。",
        info,
    )


def _leaf_ratio(img: np.ndarray) -> float:
    """计算图片中绿色/黄绿色像素占比。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, _HSV_LOWER, _HSV_UPPER)
    total = mask.shape[0] * mask.shape[1]
    if total == 0:
        return 0.0
    return float(cv2.countNonZero(mask)) / total


def _background_uniformity(img: np.ndarray) -> Tuple[float, float]:
    """计算图片四周边缘带的颜色标准差和主导色占比。

    纯色背景（白/灰/单色）：标准差低、主导色占比高；
    真实田间、纹理布料、杂乱背景：标准差高、主导色占比低。
    轻微阴影/褶皱的白纸：标准差可能略高，但主导色占比仍高。
    """
    h, w = img.shape[:2]
    bh = max(1, int(h * BACKGROUND_BAND))
    bw = max(1, int(w * BACKGROUND_BAND))

    samples = [
        img[0:bh, :].reshape(-1, 3),
        img[h - bh:h, :].reshape(-1, 3),
        img[:, 0:bw].reshape(-1, 3),
        img[:, w - bw:w].reshape(-1, 3),
    ]
    bg = np.concatenate(samples, axis=0).astype(np.float32)
    if len(bg) == 0:
        return 9999.0, 0.0

    mean = bg.mean(axis=0)
    std = float(bg.std(axis=0).mean())

    distances = np.linalg.norm(bg - mean, axis=1)
    dominant = float(np.mean(distances <= BACKGROUND_MAX_DISTANCE))
    return std, dominant


def _is_uniform_background(std: float, dominant_ratio: float) -> bool:
    """判断背景是否为纯色。

    严格条件：标准差足够低；
    宽松条件：标准差略高，但主色附近像素占比足够高（允许轻微阴影/褶皱）。
    """
    if std <= BACKGROUND_MAX_STD:
        return True
    if std <= BACKGROUND_MAX_STD_LOOSE and dominant_ratio >= BACKGROUND_DOMINANT_RATIO:
        return True
    return False


# ----------------- 叶片前景掩膜（供病灶热力图约束使用） -----------------
# 目标：从「单叶 + 纯色背景」的照片里抠出叶片前景，用于 Grad-CAM 热力图的
# 背景抑制——只允许在叶片上画热力，避免纯白背景 / 地板砖缝等被误当成病灶。
FG_MORPH_KERNEL = 7          # 形态学核大小（闭运算连接断裂、膨胀收边）
FG_MIN_AREA_RATIO = 0.004    # 连通域最小面积占比，过滤噪点
FG_DILATE_ITERS = 2          # 膨胀轮数，让叶缘也纳入前景


def leaf_foreground_mask(img: np.ndarray) -> np.ndarray:
    """提取叶片前景掩膜（与原图同尺寸，uint8 0/255）。

    思路：
    1. 用绿色 HSV 掩膜定位叶片主体；
    2. 闭运算 + 开运算连接断裂、去除噪点；
    3. 按连通域面积过滤，只保留足够大的叶片区域；
    4. 对每个连通域做「凸包填充」：
       - 叶片内部被病斑挖空的洞会被补回前景；
       - 叶缘病灶（褐/黑/黄/白，不在绿色范围）所在的叶缘凹陷会被凸包拉直并覆盖，
         解决「边缘病灶被裁切」的问题；
    5. 轻微膨胀收边，让叶缘病灶边缘也被纳入。

    注意：凸包会把叶缘凹陷处的少量背景也包进前景，这是有意为之——
    真正的背景过滤交给 gradcam.py 里的「热力阈值」去做：凸包误包的背景热力低，
    不会被涂色，所以不会重新出现「背景被当成病灶」的问题。
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, _HSV_LOWER, _HSV_UPPER)

    kernel = np.ones((FG_MORPH_KERNEL, FG_MORPH_KERNEL), np.uint8)
    closed = cv2.morphologyEx(green, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)

    mask = np.zeros_like(cleaned)
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = img.shape[0] * img.shape[1] * FG_MIN_AREA_RATIO
    valid = [c for c in contours if cv2.contourArea(c) >= min_area]
    if valid:
        # 凸包填充：覆盖内部病斑空洞 + 叶缘病灶，避免边缘病灶被裁切
        hulls = [cv2.convexHull(c) for c in valid]
        cv2.drawContours(mask, hulls, -1, 255, cv2.FILLED)

    if FG_DILATE_ITERS > 0:
        mask = cv2.dilate(mask, kernel, iterations=FG_DILATE_ITERS)
    return mask
