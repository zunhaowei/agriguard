"""pytest 全局配置。

两件事：

1. **导入路径**：把 backend 加入 sys.path，使 `app` 包可被导入
   （项目源码在 backend/app/ 下，从仓库根运行时 `import app` 会失败）。

2. **库隔离（改用后端正式入口 AGRI_DB_PATH）**：
   在**任何测试代码 import `app.*` 之前**，把环境变量 `AGRI_DB_PATH`
   指向本次会话专属的临时库。该变量是后端新提供的正式入口
   （backend/app/db.py 的 `DB_PATH_ENV`），并在 db 模块 **import 时读取一次**，
   因此必须在 import 前设置 —— 而 conftest.py 的导入早于所有测试模块的导入，
   天然满足这个时机要求。

   效果：全套测试（含 test_baseline 的启动钩子）只访问临时库，
   交付库 `data/agriguard.db` 全程零访问、零污染；测试也不再依赖交付库的任何
   既有内容（临时库每次全新创建，仅播种 demo —— 等价于“交付库被重置为只剩 demo”）。
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

for p in (str(BACKEND), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# --- 会话级临时库：必须在 import app.* 之前设置 AGRI_DB_PATH ---
_TMP_DB_DIR = tempfile.mkdtemp(prefix="agri_pytest_db_")
os.environ["AGRI_DB_PATH"] = str(Path(_TMP_DB_DIR) / "agriguard.db")


def _cleanup_tmp_db() -> None:
    shutil.rmtree(_TMP_DB_DIR, ignore_errors=True)


atexit.register(_cleanup_tmp_db)
