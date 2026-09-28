"""在 1920x1920 高清病叶照片上用真实模型跑 Grad-CAM，生成真正高清的热力图素材。"""
import sys
from pathlib import Path

import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO
from backend.app.gradcam import generate_cam

ASSET = ROOT / "参赛材料" / "assets"
GEN = ROOT / "media" / "gen"

model = YOLO(str(ROOT / "models" / "best.pt"))

# 高清病叶照片
src = GEN / "leaf_disease_hi.jpg"
res = model.predict(str(src), conf=0.25)[0]
cid = int(res.probs.top5[0])
print("class:", cid, "->", res.names[cid], "conf:", round(float(res.probs.top5conf[0]), 4))

out = ASSET / "heatmap_hi.png"
# 注意：generate_cam 当前返回 Tuple[Optional[str], dict]（路径 + 量化统计），
# 早期版本只返回路径。这里必须解包，否则会把元组当路径传给 Image.open 而报
# AttributeError: 'tuple' object has no attribute 'read'。
ret, stats = generate_cam(model, str(src), cid, str(out))
print("return:", ret)
print("stats:", stats)

if ret:
    im = Image.open(ret).convert("RGB")
    print("heatmap size:", im.size, "mode:", im.mode)
    # 保存为高质量 PNG（无损）
    im.save(ASSET / "heatmap_hi.png")
    print("saved png bytes:", (ASSET / "heatmap_hi.png").stat().st_size)
else:
    print("[错误] 热力图生成失败，未产出 heatmap_hi.png")