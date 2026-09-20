"""接口数据模型（前后端契约）。

【本次审查新增的字段，以及它们各自解决的问题】

- ood_reject_threshold / ood_warn_threshold
  原先前端 app.js 把「拒识阈值 0.25」「≥0.32 为正常」**硬编码**在自己代码里，
  与后端 detector.py 的两份常量各自维护、没有任何同步机制。
  而阈值历史上调整过两次，这段文案又显示在结果区正文里——
  一旦漂移，就是答辩现场"文案说的数和实际判的数对不上"的穿帮点。
  现由后端随每次响应下发真值，前端只读不写，双份真源合并为一。

- prescription_source
  这是**诚实性字段**。处方有两条路径：大模型生成或内置模板兜底。
  原实现静默回落，外部无法分辨，容易在演示与答辩中造成"声称大模型、
  实际跑模板"的事实性风险。现显式标注来源，让界面和答辩口径都能如实呈现。

- latency_ms / model_name / model_weight_mb / device
  用于在结果区呈现"本地轻量推理"这一实际优势（模型仅 3.28MB、毫秒级、无需联网），
  这是可被现场验证的产品事实，比口头描述更有说服力。

- lesion_ratio / severity_grade
  把热力图结论从"一张彩色图"升级为"可量化的病灶面积占比 + 严重度分级"，
  使"识别 -> 定位 -> 量化 -> 分级处方"形成完整循证链。
  这两个值仅用于分级展示，不参与判识关键路径。

- work / signature
  原创作品标识，用于防抄袭取证与原创性举证（详见 constants.py 说明）。
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from . import constants


class Detection(BaseModel):
    """单条识别结果。"""

    name: str
    confidence: float
    class_id: Optional[int] = None


class Prescription(BaseModel):
    """防治处方。"""

    disease: str
    severity: str
    summary: str
    biological: str
    chemical: str
    tips: str


class PredictResponse(BaseModel):
    """`POST /api/v1/predict` 的响应体。"""

    ok: bool = True
    reason: Optional[str] = None
    warning: Optional[str] = None

    # 拍摄形式校验指标
    leaf_ratio: Optional[float] = None
    background_std: Optional[float] = None
    background_dominant_ratio: Optional[float] = None

    # 分布外检测
    ood_score: Optional[float] = None
    ood_reject_threshold: float = constants.OOD_REJECT_THRESHOLD
    ood_warn_threshold: float = constants.OOD_WARN_THRESHOLD

    # 识别与处方
    detections: List[Detection] = Field(default_factory=list)
    prescription: Optional[Prescription] = None
    prescription_source: Optional[str] = None  # "llm" | "template"

    # 可解释性量化
    heatmap_url: Optional[str] = None
    lesion_ratio: Optional[float] = None
    severity_grade: Optional[str] = None  # "轻" | "中" | "重" | "健康" | "待评估"

    # 运行时可观测性
    latency_ms: Optional[float] = None
    model_name: Optional[str] = None
    model_weight_mb: Optional[float] = None
    device: Optional[str] = None

    # 原创作品标识
    work: str = constants.WORK_ID
    signature: str = constants.ORIGIN_SIGNATURE


class MetaResponse(BaseModel):
    """`GET /api/v1/meta` 的响应体：向前端下发业务常量真值。

    前端据此渲染阈值文案与作物清单，彻底消除前后端各存一份的漂移风险。
    """

    work: str = constants.WORK_ID
    work_name: str = constants.WORK_NAME
    version: str = constants.WORK_VERSION
    signature: str = constants.ORIGIN_SIGNATURE

    supported_crops: List[str] = Field(default_factory=list)
    ood_reject_threshold: float = constants.OOD_REJECT_THRESHOLD
    ood_warn_threshold: float = constants.OOD_WARN_THRESHOLD

    max_upload_mb: float = round(constants.MAX_UPLOAD_BYTES / 1024 / 1024, 1)
    allowed_suffixes: List[str] = Field(default_factory=list)

    model_name: Optional[str] = None
    model_weight_mb: Optional[float] = None
    device: Optional[str] = None
    llm_enabled: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    model_ready: bool = False
    work: str = constants.WORK_ID
    signature: str = constants.ORIGIN_SIGNATURE
