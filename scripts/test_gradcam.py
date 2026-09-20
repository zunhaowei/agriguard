"""独立验证 Grad-CAM 热力图生成。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2

from ultralytics import YOLO

from backend.app.gradcam import generate_cam

model = YOLO(str(ROOT / "models" / "best.pt"))
val_root = ROOT / "data" / "plantvillage" / "val"
imgs = [p for p in sorted(val_root.rglob("*.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
sample = next((p for p in imgs if "healthy" not in str(p)), imgs[0])

res = model.predict(str(sample), conf=0.25)[0]
cid = int(res.probs.top5[0])
print("样本:", sample.name)
print("class_id:", cid, "->", res.names[cid])

out = ROOT / "uploads" / "test_heatmap.jpg"
ret = generate_cam(model, str(sample), cid, str(out))
print("返回:", ret)

if ret:
    img = cv2.imread(ret)
    print("热力图尺寸:", img.shape)
    print("BGR均值:", img.reshape(-1, 3).mean(axis=0).round(1))
    print("像素标准差:", round(float(img.std()), 1))
    print("文件大小:", out.stat().st_size, "bytes")