import shutil
import uuid

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIR, UPLOAD_DIR
from .detector import Detector
from .gradcam import generate_cam
from .precheck import check_leaf_and_background
from .prescriber import Prescriber
from .schemas import PredictResponse

app = FastAPI(title="禾目 AgriGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

detector = Detector()
prescriber = Prescriber()

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)):
    suffix = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{suffix}"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    ok, reason, info = check_leaf_and_background(str(path))
    if not ok:
        return PredictResponse(
            ok=False,
            reason=reason,
            leaf_ratio=info.get("leaf_ratio"),
            background_std=info.get("background_std"),
            background_dominant_ratio=info.get("background_dominant_ratio"),
        )

    detections, ood_score, is_ood, is_warning = detector.detect(str(path))

    # 分布外（OOD）拒识：图片通过了拍摄形式校验，但特征与训练分布差异过大。
    # 常见原因：训练集外物种、严重域偏移（田间实景/复杂光照/非实验室拍摄）。
    if is_ood:
        return PredictResponse(
            ok=False,
            reason="模型对当前图片不够确信，可能不在可识别范围内。请确认叶片属于支持的作物（番茄、葡萄、玉米、马铃薯、苹果、桃、草莓、辣椒、樱桃、大豆、蓝莓、南瓜、树莓、柑橘），并在纯色背景下重新拍摄。",
            leaf_ratio=info.get("leaf_ratio"),
            background_std=info.get("background_std"),
            background_dominant_ratio=info.get("background_dominant_ratio"),
            ood_score=ood_score,
            # 方案 B：即便拒识，也把模型的原始 top3 判定返回给前端，
            # 让用户看到「模型自认为是什么」，便于人工判断而非被一刀切拒绝。
            detections=detections,
        )

    warning = None
    if is_warning:
        warning = "分布相似度偏低（%.2f），识别结果仅供参考，建议重新拍摄更清晰的纯色背景叶片图。" % ood_score

    prescription = prescriber.generate(detections)

    heatmap_url = None
    if detections and detections[0].class_id is not None:
        heat_path = UPLOAD_DIR / f"{path.stem}_heatmap.jpg"
        if generate_cam(detector.model, str(path), detections[0].class_id, str(heat_path)):
            heatmap_url = f"/uploads/{heat_path.name}"

    return PredictResponse(
        detections=detections,
        prescription=prescription,
        heatmap_url=heatmap_url,
        ood_score=ood_score,
        warning=warning,
    )