"""端到端冒烟测试：真实病叶图 → 识别 → 中文翻译 → 模板处方。

用法：.venv\\Scripts\\python.exe -B scripts\\smoke_test.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.detector import Detector
from backend.app.prescriber import Prescriber

val_root = ROOT / "data" / "plantvillage" / "val"
imgs = [p for p in sorted(val_root.rglob("*.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
sample = next((p for p in imgs if "healthy" not in str(p)), imgs[0])
print("样本文件:", sample.name)
print("真实类别:", sample.parent.name)

det = Detector()
detections = det.detect(str(sample))
print("Top3 识别:")
for d in detections:
    print(f"  {d.name}  ({d.confidence:.4f})")

pres = Prescriber()._generate_from_template(detections[0])
print("模板处方:")
for f in ("disease", "severity", "summary", "biological", "chemical", "tips"):
    print(f"  {f}: {getattr(pres, f)}")