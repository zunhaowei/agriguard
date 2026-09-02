"""临时探查 YOLO11-cls 模型结构，确定 Grad-CAM 目标层。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO

m = YOLO(str(ROOT / "models" / "best.pt"))
mm = m.model
print("type(m.model):", type(mm))
print("has .model:", hasattr(mm, "model"))
inner = mm.model if hasattr(mm, "model") else mm
print("type(inner):", type(inner))
print("--- structure ---")
print(inner)
print("--- fc/head ---")
for name in ("fc", "classifier", "head", "names", "nc"):
    if hasattr(mm, name):
        v = getattr(mm, name)
        print(f"{name}: {type(v)} -> {v if not hasattr(v,'__len__') or (hasattr(v,'__len__') and ( isinstance(v,(int,)) or len(str(v))<200 )) else str(v)[:200]}")