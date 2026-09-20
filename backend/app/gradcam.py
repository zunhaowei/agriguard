"""Grad-CAM++ 病灶定位可视化：高亮分类模型关注的局部区域。

对 YOLO11n-cls 分类模型做可解释热力图。目标层为分类头前的最后一个
空间特征层（C2PSA，256 通道），并用分类头 linear 输出的原始 logits
（跳过 softmax）反向传播，避免 softmax 饱和导致的梯度消失。

方案 C 升级（对比标准 Grad-CAM）：
1. 输入分辨率 224 -> 640：目标层特征图从 7x7 提升到 20x20，空间精度
   提升约 8 倍，小病灶也能被定位；
2. Grad-CAM -> Grad-CAM++：对每个像素分配独立的权重系数 alpha，
   对「多片/重叠/弱但真实」的病灶区域给予更强热力，减少只高亮
   最显著一片而漏掉其它病灶的问题；
3. 阈值自适应（Otsu + 保护区间）：不再用 0.25 一刀切，而是按每张图
   叶片内热力分布自动选取阈值，弱病灶不会被固定阈值滤掉。

方案 F 升级（对比方案 C）：
4. 叠加「色温异常检测通道」：Grad-CAM 本质是「分类判别性可视化」，
   只高亮对分类最关键的局部特征，会漏掉「末期大面积坏死 / 严重变色」
   等对类别判别贡献低、但视觉上明显是病灶的区域。本通道在叶片前景内
   统计健康叶色的 HSV 分布（均值 + 协方差），用 Mahalanobis 距离度量
   每个像素偏离健康叶色的程度，超出阈值的像素被直接抬升到 JET 色带的
   暖色端（红），整体仍保持「冷色→暖色」的单一过渡、不引入额外颜色；
   同时排除白色背景/高光（低饱和 + 高亮），避免把背景白误标为病灶。
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import torch

from .model_arch import resolve_backbone
from .precheck import leaf_foreground_mask

logger = logging.getLogger(__name__)

# 本次审查修正：原先此处硬编码 `_TARGET_LAYER = 9` / `_HEAD_LAYER = 10`，
# 与 detector.py 的 `children()[-1]` 构成两套不一致的寻址约定，且会随 backbone
# 或 ultralytics 版本变化而**静默指向错误的层**（不报错，但热力图语义全错）。
# 现统一改为按模块类型/属性内省定位，见 model_arch.resolve_backbone()。
_IMGSZ = 640        # 可视化前向分辨率（目标层特征图 20x20）

_THRESHOLD_MIN = 0.12   # Otsu 自适应阈值下限保护（避免热力过弱时仍涂色）
_THRESHOLD_MAX = 0.50   # Otsu 自适应阈值上限保护（避免只有微弱响应时涂满全叶）

# ----------------- 方案 F：色温异常检测通道 -----------------
_ENABLE_COLOR_ANOMALY = True   # 是否启用色温异常通道（可快速关闭对比）
_HEALTHY_H = (25, 100)         # 健康叶色的 HSV 范围（与 precheck 一致）
_HEALTHY_S = (40, 255)
_HEALTHY_V = (40, 255)
_ANOMALY_SIGMA = 3.0           # Mahalanobis 距离阈值（约 3σ）
_ANOMALY_MIN_HEALTHY = 200     # 健康绿色像素最少数量，低于则统计不可靠、不启用
_ANOMALY_HEAT = 0.85           # 色温异常区在 JET 色带中抬升到的热力值（暖色端）
_WHITE_S_MAX = 30              # 饱和度低于此值视为无彩（白/灰/高光），排除出病灶
_WHITE_V_MIN = 180             # 亮度高于此值视为白色背景/高光，排除出病灶


def _otsu_threshold(vals: np.ndarray) -> float:
    """对归一化热力值（0~1）计算 Otsu 阈值，自动分离「病灶高亮 / 健康低亮」。

    Otsu 假设叶片内热力呈双峰分布（病灶高、健康低），取使类间方差最大的
    分界值。若输入过少则回落到下限保护值。
    """
    if vals.size < 2:
        return _THRESHOLD_MIN
    hist, _ = np.histogram(vals, bins=64, range=(0.0, 1.0))
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return _THRESHOLD_MIN

    centers = (np.arange(64) + 0.5) / 64.0
    sum_all = float((centers * hist).sum())

    w_b = 0.0
    sum_b = 0.0
    max_var = -1.0
    threshold = _THRESHOLD_MIN
    for t in range(64):
        w_b += hist[t]
        if w_b <= 0:
            continue
        w_f = total - w_b
        if w_f <= 0:
            break
        sum_b += centers[t] * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = centers[t]
    return float(threshold)


def _color_anomaly_mask(img: np.ndarray, fg_mask: np.ndarray) -> Optional[np.ndarray]:
    """检测叶片前景内「明显偏离健康叶色」的像素，返回 uint8 0/255 掩膜。

    原理（方案 F）：
    1. 在叶片前景内，用健康叶色的 HSV 范围筛出「仍健康的绿色像素」；
    2. 统计这些健康像素的 HSV 均值 mu 与协方差 cov；
    3. 对前景内每个像素计算 Mahalanobis 距离 d = sqrt((x-mu)ᵀ cov⁻¹ (x-mu))，
       d 越大说明颜色越偏离健康叶色（深褐/黑坏死、严重黄化/白化等）；
    4. d > sigma 的像素判为「色温异常区」，形态学去噪后输出。

    返回 None 表示健康绿色像素太少（如全叶已枯黄/坏死），统计不可靠，
    此时不启用色温异常通道，避免误判。
    """
    if not _ENABLE_COLOR_ANOMALY:
        return None

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, w = img.shape[:2]

    lower = np.array([_HEALTHY_H[0], _HEALTHY_S[0], _HEALTHY_V[0]], np.uint8)
    upper = np.array([_HEALTHY_H[1], _HEALTHY_S[1], _HEALTHY_V[1]], np.uint8)
    green = cv2.inRange(hsv.astype(np.uint8), lower, upper)  # (H,W) 0/255
    healthy = (green > 0) & (fg_mask > 0)

    if int(healthy.sum()) < _ANOMALY_MIN_HEALTHY:
        return None

    vals = hsv[healthy]                      # (N,3)
    mu = vals.mean(axis=0)                   # (3,)
    cov = np.cov(vals.T) + np.eye(3) * 1e-2  # (3,3) 加正则保证可逆
    try:
        cov_inv = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        return None

    fg_flat = hsv[fg_mask > 0]               # (M,3)
    diff = fg_flat - mu                      # (M,3)
    mahal = np.sqrt(np.einsum('ij,jk,ik->i', diff, cov_inv, diff))  # (M,)

    # 白色背景 / 高光抑制：低饱和 + 高亮 是白纸/白瓷砖/白墙/强反光，
    # 不是病灶，即使偏离健康叶色也不标为异常，避免热力铺到背景上。
    s_full = hsv[:, :, 1]
    v_full = hsv[:, :, 2]
    white_mask = (s_full < _WHITE_S_MAX) & (v_full > _WHITE_V_MIN)  # 全图白色掩膜
    s_flat = fg_flat[:, 1]
    v_flat = fg_flat[:, 2]
    white = (s_flat < _WHITE_S_MAX) & (v_flat > _WHITE_V_MIN)

    anomaly = np.zeros((h, w), np.uint8)
    anomaly[fg_mask > 0] = ((mahal > _ANOMALY_SIGMA) & (~white)).astype(np.uint8) * 255

    # 形态学去噪：开运算去孤立噪点，闭运算连接邻近异常块
    anomaly = cv2.morphologyEx(anomaly, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    anomaly = cv2.morphologyEx(anomaly, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    # 闭运算会把邻近的白色背景像素一并扩散进来，最后再清一次
    anomaly[white_mask] = 0
    return anomaly


def generate_cam(
    yolo_model, image_path: str, class_idx: int, out_path: str
) -> Tuple[Optional[str], dict]:
    """生成 Grad-CAM++ 热力图叠加图，保存到 out_path。

    返回 `(out_path 或 None, stats)`。
    `stats` 即使失败也返回（可能为空字典），包含：
    - `lesion_ratio`：叶片前景内被判定为病灶的像素占比（0~1）
    - `anomaly_ratio`：色温异常通道命中的像素占前景比例（0~1）
    - `foreground_ratio`：叶片前景占全图比例（0~1）

    这些量化值使"识别 -> 定位 -> 量化 -> 分级处方"形成完整循证链。
    失败（图片损坏 / 梯度异常 / 结构不符）时返回 `(None, stats)` 并记录日志——
    原先此处 `except Exception: return None` 完全静默，导致演示中"功能悄悄消失"
    却无从定位。
    """
    stats: dict = {}
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.warning("热力图跳过：无法读取图片 %s", image_path)
            return None, stats
        orig_h, orig_w = img.shape[:2]

        # ---- 几何一致性修正（本次审查新增，正确性缺陷） ----
        # 背景：识别路径走的是 ultralytics 分类预处理「短边缩放 + 中心裁剪」，
        # 而原可视化路径走的是「直接拉伸到 640×640」，最后又把 CAM 拉回**整图**。
        # 两条路径看到的**内容范围不同**：对于非正方形图片，识别看的是中心正方形区域，
        # 热力图却按整图铺开 —— 病灶位置会画错。
        # 项目自带的示例图恰好是 256×256 正方形，两条路径等价，所以此前无人发现。
        #
        # 修正：可视化也采用与识别一致的几何（短边缩放 + 中心裁剪），
        # CAM 生成后再映射回原图对应的中心方形区域，保证"识别看到的"与
        # "热力图标注的"是同一块内容。
        crop_side = min(orig_h, orig_w)
        crop_x0 = (orig_w - crop_side) // 2
        crop_y0 = (orig_h - crop_side) // 2
        square = img[crop_y0:crop_y0 + crop_side, crop_x0:crop_x0 + crop_side]
        rgb = cv2.cvtColor(cv2.resize(square, (_IMGSZ, _IMGSZ)), cv2.COLOR_BGR2RGB)

        model = yolo_model.model  # ClassificationModel
        model.eval()
        device = next(model.parameters()).device

        # 加载后的权重 requires_grad=False，需临时启用以便反向传播。
        # 注意：这是对共享模型的全局状态切换，调用方必须用推理锁串行化，
        # 否则并发调用会互相干扰（见 main.py 的 _model_lock 说明）。
        orig_grad = [p.requires_grad for p in model.parameters()]
        for p in model.parameters():
            p.requires_grad_(True)

        x = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to(device)

        view = resolve_backbone(yolo_model)
        target = view.target
        head = view.head
        acts: dict = {}
        raw_logits: dict = {}

        def fwd_hook(_m, _inp, out):
            acts["v"] = out

        def head_hook(_m, _inp, out):
            raw_logits["v"] = out

        h1 = target.register_forward_hook(fwd_hook)
        h2 = head.linear.register_forward_hook(head_hook)
        try:
            model(x)

            act = acts["v"]                      # (1,C,H,W)
            logits = raw_logits["v"]             # (1,nc) 原始 logits（未经过 softmax）
            if logits.dim() == 1:
                logits = logits.unsqueeze(0)
            cid = int(class_idx)
            if cid < 0 or cid >= logits.shape[1]:
                cid = int(logits[0].argmax())

            grad = torch.autograd.grad(logits[0, cid], act, retain_graph=False)[0]  # (1,C,H,W)

            # ---- Grad-CAM++ 逐像素权重 ----
            g2 = grad * grad
            g3 = g2 * grad
            sum_act_g3 = (act * g3).sum(dim=(2, 3), keepdim=True)  # (1,C,1,1)
            alpha = g2 / (2.0 * g2 + sum_act_g3 + 1e-7)
            w = (alpha * torch.relu(grad)).sum(dim=(2, 3), keepdim=True)  # (1,C,1,1)

            cam = torch.relu((w * act).sum(dim=1))   # (1,H,W)
            cam = cam[0].detach().cpu().numpy()
            cam -= cam.min()
            if cam.max() > 1e-8:
                cam /= cam.max()

            # 把 CAM 映射回原图：先缩放到中心方形区域，再贴进整图尺寸的画布。
            # 中心方形之外的内容没有参与模型推理，热力必须留 0，
            # 否则会出现"在被裁掉的那部分图片上也画了热力"的越界错误。
            cam_square = cv2.resize(
                cam, (crop_side, crop_side), interpolation=cv2.INTER_CUBIC
            ).astype(np.float32)
            cam = np.zeros((orig_h, orig_w), np.float32)
            cam[crop_y0:crop_y0 + crop_side, crop_x0:crop_x0 + crop_side] = cam_square

            # 前景掩膜约束：把背景响应归零，只保留叶片区域的热力
            fg_mask = leaf_foreground_mask(img)  # (H,W) uint8 0/255
            fg = fg_mask.astype(np.float32) / 255.0
            fg_bool = fg > 0.5
            cam = cam * fg

            # ---- 合成最终图：单一 JET 冷→暖过渡，无额外颜色 ----
            # 1) 色温异常区（末期坏死/严重变色）：把该区域热力值抬升到暖色端，
            #    让它在 JET 色带里自然显示为红/深红，与 Grad-CAM 强热力同色系。
            #
            # 本次审查修正：此处原先有一次「先算 Otsu 得到 heat_color、随后立即被
            # 下一段覆盖」的无效计算，属死代码，已移除。有效阈值只在异常区抬升后算一次。
            anomaly = _color_anomaly_mask(img, fg_mask)
            # 抬升前先快照纯 Grad-CAM 热力，用于统计两条通道各自的着色贡献。
            # 必要性：审查实测发现当前样图的着色像素里有约 96.6% 来自色温异常通道、
            # 仅约 4.0% 来自 Grad-CAM++ 本体。若不把贡献量化出来并如实标注，
            # 对外宣称"Grad-CAM++ 定位病灶"与实际输出不符 —— 这是答辩可被追问的技术准确性问题。
            cam_gradcam_only = cam.copy()
            if anomaly is not None and int(anomaly.sum()) > 0:
                anomaly_f = (anomaly > 0).astype(np.float32)
                cam = np.maximum(cam, anomaly_f * _ANOMALY_HEAT)

            # 2) 自适应阈值（基于抬升后的热力分布）：只对「前景内 && 热力高于阈值」
            #    的像素涂色，于是凸包误包进来的背景（热力低）与叶片健康区都保持原图。
            #    注：异常区已抬升到 _ANOMALY_HEAT=0.85，远高于阈值上限 0.50，
            #    因此必被涂色——这是有意设计，保证"末期坏死"一定可见。
            fg_vals = cam[fg_bool]
            thr = _otsu_threshold(fg_vals) if fg_vals.size else _THRESHOLD_MIN
            thr = float(np.clip(thr, _THRESHOLD_MIN, _THRESHOLD_MAX))
            heat_color = fg_bool & (cam > thr)

            # 3) JET 热力叠加：异常区（已抬升为暖色）与 Grad-CAM 强响应统一走同一色带
            heat = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
            blended = cv2.addWeighted(img, 0.55, heat, 0.45, 0)
            final = img.copy()
            final[heat_color] = blended[heat_color]

            # 4) 量化统计：把"一张彩色图"变成可用的数字，供严重度分级与前端展示，
            #    并如实暴露两条通道各自的着色贡献（见上面对贡献比的说明）。
            fg_px = float(np.count_nonzero(fg_bool)) or 1.0
            heat_px = float(np.count_nonzero(heat_color)) or 1.0
            gradcam_px = float(np.count_nonzero(heat_color & (cam_gradcam_only > thr)))
            stats = {
                "lesion_ratio": round(float(np.count_nonzero(heat_color)) / fg_px, 4),
                "anomaly_ratio": (
                    round(float(np.count_nonzero(anomaly > 0)) / fg_px, 4)
                    if anomaly is not None
                    else 0.0
                ),
                "foreground_ratio": round(fg_px / float(orig_h * orig_w or 1), 4),
                # 两条通道对最终着色面积的贡献占比（0~1）
                "gradcam_contrib": round(gradcam_px / heat_px, 4),
                "color_anomaly_contrib": round((heat_px - gradcam_px) / heat_px, 4),
            }

            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(out_path, final)
            return out_path, stats
        finally:
            h1.remove()
            h2.remove()
            for p, og in zip(model.parameters(), orig_grad):
                p.requires_grad_(og)
    except Exception:
        # 原实现此处静默 return None，导致系统性失败（层不匹配 / 显存不足）在
        # 演示中表现为"功能悄悄消失"却无从定位。现记录完整堆栈。
        logger.exception("热力图生成失败 path=%s class_idx=%s", image_path, class_idx)
        return None, stats
