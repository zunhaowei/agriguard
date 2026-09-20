"""测试 precheck 阈值：对单张图片输出 leaf_ratio 和 background_std。

用法：
  .venv\Scripts\python.exe scripts\test_precheck.py <图片路径>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.precheck import check_leaf_and_background

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "frontend" / "_demo_leaf.jpg"
ok, reason, info = check_leaf_and_background(str(path))
print(f"图片: {path}")
print(f"通过: {ok}")
print(f"原因: {reason}")
print(
    f"指标: leaf_ratio={info.get('leaf_ratio')}, "
    f"background_std={info.get('background_std')}, "
    f"background_dominant_ratio={info.get('background_dominant_ratio')}"
)
