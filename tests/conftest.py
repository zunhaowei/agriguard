"""pytest 全局配置：把 backend 加入导入路径，使 `app` 包可被导入。

为什么需要：项目源码在 backend/app/ 下，而 pytest 从仓库根运行时
`import app` 会失败。这里显式注入路径，避免依赖 cwd 或环境变量。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

for p in (str(BACKEND), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
