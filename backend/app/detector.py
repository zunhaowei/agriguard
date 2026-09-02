from typing import List, Tuple

import torch
import torch.nn.functional as F
from ultralytics import YOLO

from .config import MODEL_PATH, FALLBACK_MODEL
from .schemas import Detection

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


class Detector:
    def __init__(self):
        self.model = None
        self._penultimate_features = None
        self._class_weights_norm = None

        # OOD 双阈值策略：
        # - 低于 0.25：明确分布外（OOD），直接拒识（但返回模型 top3 供参考）；
        # - 0.25 ~ 0.32：灰色地带，返回识别结果但附加「仅供参考」警告；
        # - 高于等于 0.32：正常识别。
        # 标定依据：合规番茄图约 0.43，轻微模糊/色温偏移约 0.37，
        # 枫叶 0.33，合成椭圆 0.26，葡萄叶 0.19，严重域偏移田间图 0.17-0.20。
        # 注：原阈值 0.35/0.40 过严，会把支持作物（如葡萄叶）误杀，故下调。
        self.ood_reject_threshold = 0.25
        self.ood_warn_threshold = 0.32

    def load(self):
        if MODEL_PATH.exists():
            self.model = YOLO(str(MODEL_PATH))
        else:
            self.model = YOLO(FALLBACK_MODEL)

        # 注册 hook 获取分类层前的 1280-d 特征
        classify = list(self.model.model.model.children())[-1]
        classify.conv.register_forward_hook(self._hook_fn)

        # 预计算归一化的分类权重，用于 OOD 检测
        W = classify.linear.weight.detach().float()
        self._class_weights_norm = F.normalize(W, dim=1)

    def _hook_fn(self, module, input, output):
        """提取分类头 conv 输出，经 GAP 后作为 1280-d 特征向量。"""
        classify = list(self.model.model.model.children())[-1]
        pooled = classify.pool(output).view(-1)
        self._penultimate_features = pooled.detach()

    def _ood_score(self) -> float:
        """计算当前已提取特征与所有类别权重向量的最大余弦相似度。"""
        if self._penultimate_features is None or self._class_weights_norm is None:
            return 0.0
        z = self._penultimate_features
        z_norm = F.normalize(z.unsqueeze(0), dim=1)
        sims = torch.matmul(z_norm, self._class_weights_norm.t()).squeeze(0)
        return float(sims.max())

    def detect(self, image_path: str) -> Tuple[List[Detection], float, bool, bool]:
        if self.model is None:
            self.load()
        results = self.model.predict(image_path, conf=0.25, verbose=False)[0]
        detections: List[Detection] = []

        if results.probs is not None:
            for i in range(min(3, len(results.probs.top5))):
                cls_id = int(results.probs.top5[i])
                conf = float(results.probs.top5conf[i])
                detections.append(
                    Detection(
                        name=_translate(results.names[cls_id]),
                        confidence=round(conf, 4),
                        class_id=cls_id,
                    )
                )
        else:
            for box in results.boxes:
                cls_id = int(box.cls[0])
                detections.append(
                    Detection(
                        name=_translate(results.names[cls_id]),
                        confidence=round(float(box.conf[0]), 4),
                        class_id=cls_id,
                    )
                )

        ood_score = self._ood_score()
        is_ood = ood_score < self.ood_reject_threshold
        is_warning = self.ood_reject_threshold <= ood_score < self.ood_warn_threshold
        return detections, round(ood_score, 4), is_ood, is_warning