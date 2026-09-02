"""校验 best.pt 的类别名与 detector 的中文映射完全对齐。

用法：.venv\\Scripts\\python.exe -B scripts\\verify_mapping.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO

from backend.app.detector import _CN_BY_NAME, _translate

model = YOLO(str(ROOT / "models" / "best.pt"))
name_set = set(dict(model.names).values())

missing = [n for n in name_set if n not in _CN_BY_NAME]
extra = [n for n in _CN_BY_NAME if n not in name_set]

print(f"模型类别数: {len(name_set)}")
print(f"映射表条目: {len(_CN_BY_NAME)}")
print(f"未映射(缺): {missing}")
print(f"多余(表有模型无): {extra}")
print("--- 逐类翻译 ---")
for n in sorted(name_set):
    print(f"  {n!r} => {_translate(n)!r}")