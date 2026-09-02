"""分析 uploads/ 目录里的所有唯一上传图。

输出：每张图的
- 文件大小 / 尺寸
- precheck 指标（leaf_ratio, background_std, background_dominant_ratio, ok）
- 模型 top3 预测（名称、置信度）
"""
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.precheck import check_leaf_and_background
from app.detector import Detector

UPLOADS = Path(__file__).parent.parent / "uploads"
OUTPUT = Path(__file__).parent.parent / "uploads_analysis.json"

detector = Detector()

# 只分析原图，跳过 _heatmap 图
images = sorted(p for p in UPLOADS.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png") and "_heatmap" not in p.name)

rows = []
for p in images:
    img = cv2.imread(str(p))
    if img is None:
        continue
    h, w = img.shape[:2]
    ok, reason, info = check_leaf_and_background(str(p))
    dets, ood_score, is_ood, is_warning = detector.detect(str(p))
    top3 = [{"name": d.name, "confidence": round(d.confidence, 6)} for d in dets[:3]]
    rows.append({
        "filename": p.name,
        "size": p.stat().st_size,
        "width": w,
        "height": h,
        "ok": ok,
        "reason": reason,
        "leaf_ratio": info.get("leaf_ratio"),
        "background_std": info.get("background_std"),
        "background_dominant_ratio": info.get("background_dominant_ratio"),
        "ood_score": ood_score,
        "is_ood": is_ood,
        "top3": top3,
    })

OUTPUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"分析完成，结果已写入 {OUTPUT}")
