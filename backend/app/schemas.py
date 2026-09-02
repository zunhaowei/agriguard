from typing import List, Optional

from pydantic import BaseModel


class Detection(BaseModel):
    name: str
    confidence: float
    class_id: Optional[int] = None


class Prescription(BaseModel):
    disease: str
    severity: str
    summary: str
    biological: str
    chemical: str
    tips: str


class PredictResponse(BaseModel):
    ok: bool = True
    reason: Optional[str] = None
    warning: Optional[str] = None
    leaf_ratio: Optional[float] = None
    background_std: Optional[float] = None
    background_dominant_ratio: Optional[float] = None
    ood_score: Optional[float] = None
    detections: List[Detection] = []
    prescription: Optional[Prescription] = None
    heatmap_url: Optional[str] = None