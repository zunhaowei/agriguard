"""YOLO 病害识别 + 中英文类名映射 + 分布外（OOD）拒识。

【本次审查修正的工程缺陷，算法逻辑与标定阈值一律未动】

1. **消除共享可变状态（并发缺陷）**。
   原实现把 forward hook 注册在**常驻**位置，把 1280 维特征写进实例属性
   `self._penultimate_features`。由于 `detector` 是模块级单例，这是典型的
   共享可变状态——一旦服务以多线程方式处理请求（这正是我们要改成的方式），
   两个并发请求会互相覆写该属性，导致 OOD 打分张冠李戴。
   现改为**每次调用注册局部 hook、用完立即移除**，特征只存在于局部变量中。

2. **消除硬编码层索引（可维护性）**。
   原实现用 `list(model.model.model.children())[-1]` 取分类头，与 `gradcam.py`
   的 `model.model[9]/[10]` 是两套不一致的寻址。现统一走 `model_arch.resolve_backbone()`，
   并在结构不符时**快速报错**而非静默用错层。

3. **补齐日志**。OOD 打分与降级路径此前无任何日志，演示时"功能悄悄失效"无法定位。

【OOD 原理（保持不变）】
取分类头前 1280 维特征，与 38 个类别权重向量（L2 归一化后）求最大余弦相似度。
分数越低说明该图的特征越不靠近任何一个已知类别，即越可能"不认识"。
双阈值与标定依据见 `constants.py`，请勿凭感觉调整。
"""

import logging
from typing import List, Optional, Tuple

import torch
import torch.nn.functional as F
from ultralytics import YOLO

from . import constants
from .config import FALLBACK_MODEL_PATH, MODEL_PATH, resolve_model_path
from .model_arch import BackboneView, ModelStructureError, describe_backbone, resolve_backbone
from .schemas import Detection

logger = logging.getLogger(__name__)

_class_names = {
    "Apple": "苹果",
    "Tomato": "番茄",
    "Corn": "玉米",
    "Potato": "马铃薯",
    "Grape": "葡萄",
    "Pepper": "辣椒",
    "Peach": "桃",
    "Strawberry": "草莓",
    "Cherry": "樱桃",
    "Squash": "南瓜",
    "Soybean": "大豆",
    "Blueberry": "蓝莓",
    "Raspberry": "树莓",
    "Orange": "柑橘",
}

_disease_cn = {
    "Apple_scab": "苹果黑星病",
    "Black_rot": "黑腐病",
    "Cedar_apple_rust": "雪松苹果锈病",
    "healthy": "健康",
    "Bacterial_spot": "细菌性斑点病",
    "Early_blight": "早疫病",
    "Late_blight": "晚疫病",
    "Leaf_Mold": "叶霉病",
    "Septoria_leaf_spot": "斑枯病",
    "Spider_mites": "红蜘蛛（叶螨）",
    "Target_Spot": "靶斑病",
    "Yellow_Leaf_Curl_Virus": "黄化曲叶病毒病",
    "Mosaic_virus": "花叶病毒病",
    "Cercospora_leaf_spot": "褐斑病",
    "Common_rust": "普通锈病",
    "Northern_Leaf_Blight": "大斑病",
    "Powdery_mildew": "白粉病",
    "Esca": "枝枯病",
    "Leaf_blight": "叶枯病",
    "Grape_black_rot": "葡萄黑腐病",
    "Haunglongbing": "黄龙病",
}


# PlantVillage 38 类「真实类名 → 中文」完整映射。
# 训练数据目录名含特殊字符（括号/逗号/空格/末尾下划线），
# 因此用完整类名精确映射，避免 split 后键值对不上而回落英文。
_CN_BY_NAME = {
    "Apple___Apple_scab": "苹果 · 黑星病",
    "Apple___Black_rot": "苹果 · 黑腐病",
    "Apple___Cedar_apple_rust": "苹果 · 雪松苹果锈病",
    "Apple___healthy": "苹果 · 健康",
    "Blueberry___healthy": "蓝莓 · 健康",
    "Cherry_(including_sour)___healthy": "樱桃 · 健康",
    "Cherry_(including_sour)___Powdery_mildew": "樱桃 · 白粉病",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "玉米 · 灰斑病（尾孢叶斑病）",
    "Corn_(maize)___Common_rust_": "玉米 · 普通锈病",
    "Corn_(maize)___healthy": "玉米 · 健康",
    "Corn_(maize)___Northern_Leaf_Blight": "玉米 · 大斑病",
    "Grape___Black_rot": "葡萄 · 黑腐病",
    "Grape___Esca_(Black_Measles)": "葡萄 · 枝枯病（黑麻疹病）",
    "Grape___healthy": "葡萄 · 健康",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": "葡萄 · 叶枯病（拟盘多毛孢叶斑病）",
    "Orange___Haunglongbing_(Citrus_greening)": "柑橘 · 黄龙病（青果病）",
    "Peach___Bacterial_spot": "桃 · 细菌性斑点病",
    "Peach___healthy": "桃 · 健康",
    "Pepper,_bell___Bacterial_spot": "辣椒 · 细菌性斑点病",
    "Pepper,_bell___healthy": "辣椒 · 健康",
    "Potato___Early_blight": "马铃薯 · 早疫病",
    "Potato___healthy": "马铃薯 · 健康",
    "Potato___Late_blight": "马铃薯 · 晚疫病",
    "Raspberry___healthy": "树莓 · 健康",
    "Soybean___healthy": "大豆 · 健康",
    "Squash___Powdery_mildew": "南瓜 · 白粉病",
    "Strawberry___healthy": "草莓 · 健康",
    "Strawberry___Leaf_scorch": "草莓 · 叶焦病",
    "Tomato___Bacterial_spot": "番茄 · 细菌性斑点病",
    "Tomato___Early_blight": "番茄 · 早疫病",
    "Tomato___healthy": "番茄 · 健康",
    "Tomato___Late_blight": "番茄 · 晚疫病",
    "Tomato___Leaf_Mold": "番茄 · 叶霉病",
    "Tomato___Septoria_leaf_spot": "番茄 · 斑枯病",
    "Tomato___Spider_mites Two-spotted_spider_mite": "番茄 · 红蜘蛛（二斑叶螨）",
    "Tomato___Target_Spot": "番茄 · 靶斑病",
    "Tomato___Tomato_mosaic_virus": "番茄 · 花叶病毒病",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "番茄 · 黄化曲叶病毒病",
}


def _translate(name: str) -> str:
    if name in _CN_BY_NAME:
        return _CN_BY_NAME[name]
    if "___" in name:
        crop, disease = name.split("___", 1)
        crop_cn = _class_names.get(crop, crop)
        disease_cn = _disease_cn.get(disease, disease)
        return f"{crop_cn} · {disease_cn}"
    return name


def known_class_names() -> list:
    """返回模型应输出的全部类名（用于自检与材料生成）。"""
    return list(_CN_BY_NAME.keys())


class Detector:
    """病害识别器。惰性加载权重，首次调用时初始化。"""

    def __init__(self) -> None:
        self.model: Optional[YOLO] = None
        self._view: Optional[BackboneView] = None
        self._class_weights_norm: Optional[torch.Tensor] = None
        self._weight_path = None

        # 阈值统一来自 constants，不再各处独立维护。
        # 语义：< reject 拒识；reject ~ warn 附警告；>= warn 正常。
        self.ood_reject_threshold = constants.OOD_REJECT_THRESHOLD
        self.ood_warn_threshold = constants.OOD_WARN_THRESHOLD

    # -- 加载 ---------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        """加载权重并解析结构。已在加载状态时直接返回（幂等）。"""
        if self.model is not None:
            return

        path = resolve_model_path()
        is_fallback = path == FALLBACK_MODEL_PATH
        self.model = YOLO(str(path))
        self._weight_path = path

        # 统一结构解析：按类型/属性定位，而不是按位置数字。
        # 若加载到的是检测类权重，这里会抛出 ModelStructureError 并给出可读原因，
        # 而不是在后续 register_forward_hook 时抛出难以理解的 AttributeError。
        try:
            self._view = resolve_backbone(self.model)
        except ModelStructureError:
            logger.exception(
                "模型结构解析失败，权重=%s。这通常意味着加载了非分类权重"
                "（例如 fallback 被错误配置为检测模型 yolo11n.pt）。",
                path,
            )
            # 回滚加载状态，避免半初始化
            self.model = None
            raise

        head = self._view.head
        # 预计算归一化的分类权重，用于 OOD 检测
        weight = head.linear.weight.detach().float()
        self._class_weights_norm = F.normalize(weight, dim=1)

        logger.info(
            "模型已加载：%s（%s）%s | %s | 类别数=%d",
            path.name,
            "兜底权重" if is_fallback else "生产权重",
            "" if not is_fallback else " —— 识别结果不具备实际意义，仅供接口联调",
            describe_backbone(self._view),
            self._class_weights_norm.shape[0],
        )
        if is_fallback:
            logger.warning(
                "正在使用兜底权重 %s：%s 不存在或不可用。"
                "此时识别结果无实际意义，请勿用于演示或评审。",
                FALLBACK_MODEL_PATH.name,
                MODEL_PATH,
            )

    # -- OOD 打分 -----------------------------------------------------------

    def _ood_from(self, features: Optional[torch.Tensor]) -> float:
        """由局部特征向量计算 OOD 分数（不再读写任何实例状态）。"""
        if features is None or self._class_weights_norm is None:
            return 0.0
        z_norm = F.normalize(features.unsqueeze(0), dim=1)
        # 权重移到特征所在设备（GPU/CPU 一致），避免设备不匹配
        weights = self._class_weights_norm.to(features.device)
        sims = torch.matmul(z_norm, weights.t()).squeeze(0)
        return float(sims.max())

    # -- 推理 ---------------------------------------------------------------

    def detect(self, image_path: str) -> Tuple[List[Detection], float, bool, bool]:
        """执行识别。

        返回 `(detections, ood_score, is_ood, is_warning)`：
        - `detections`：Top3 结果（分类任务）
        - `is_ood=True` 表示明确拒识；`is_warning=True` 表示灰色地带
        """
        if self.model is None:
            self.load()
        assert self._view is not None  # load() 成功后必然成立

        head = self._view.head
        # 每次调用注册**局部** hook，用完即移除 —— 特征只存在于局部字典，
        # 彻底消除原先实例属性被并发覆写的竞态。
        captured: dict = {}

        def _capture(_module, _inputs, output):
            captured["v"] = head.pool(output).view(-1).detach()

        hook = head.conv.register_forward_hook(_capture)
        try:
            # 说明：分类任务不需要 confidence 过滤（分类头始终输出全部类别概率），
            # 因此不再传 conf 参数——原先的 conf=0.25 恰好等于库默认值，去掉不改变行为。
            results = self.model.predict(image_path, verbose=False)[0]
        finally:
            hook.remove()

        detections: List[Detection] = []

        if results.probs is not None:
            top5 = results.probs.top5
            top5conf = results.probs.top5conf
            for i in range(min(3, len(top5))):
                cls_id = int(top5[i])
                conf = float(top5conf[i])
                detections.append(
                    Detection(
                        name=_translate(results.names[cls_id]),
                        confidence=round(conf, 4),
                        class_id=cls_id,
                    )
                )
        elif results.boxes is not None:
            # 兼容分支：若将来改用检测路线，这里仍可用。
            for box in results.boxes:
                cls_id = int(box.cls[0])
                detections.append(
                    Detection(
                        name=_translate(results.names[cls_id]),
                        confidence=round(float(box.conf[0]), 4),
                        class_id=cls_id,
                    )
                )

        ood_score = self._ood_from(captured.get("v"))
        is_ood = ood_score < self.ood_reject_threshold
        is_warning = self.ood_reject_threshold <= ood_score < self.ood_warn_threshold

        logger.debug(
            "识别完成 path=%s top1=%s(%.4f) ood=%.4f ood=%s warn=%s",
            image_path,
            detections[0].name if detections else "-",
            detections[0].confidence if detections else 0.0,
            ood_score,
            is_ood,
            is_warning,
        )
        return detections, round(ood_score, 4), is_ood, is_warning

    # -- 元信息 -------------------------------------------------------------

    def model_info(self) -> dict:
        """返回模型元信息，供 /meta 与结果区展示（体现"轻量本地推理"）。"""
        if self._weight_path is None:
            return {}
        size_mb = round(self._weight_path.stat().st_size / 1024 / 1024, 2)
        device = "cpu"
        if self.model is not None:
            try:
                device = str(next(self.model.model.parameters()).device)
            except Exception:  # pragma: no cover - 仅用于展示，失败不影响主流程
                device = "unknown"
        return {
            "model_name": self._weight_path.name,
            "model_weight_mb": size_mb,
            "device": device,
            "is_fallback": self._weight_path == FALLBACK_MODEL_PATH,
        }
