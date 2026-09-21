"""AGRI_DB_PATH 覆盖入口的回归测试（backend/app/db.py 的 `DB_PATH_ENV`）。

【为什么用子进程】
`AGRI_DB_PATH` 在 db 模块 **import 时读取一次**（与项目其余配置保持一致，
属预期语义）。主测试进程里的 `app.*` 早已被导入，无法在进程内重新触发解析，
所以在**子进程**里「先设变量、再 import、再建库」才能干净复现真实时序。

覆盖：
1. 设 AGRI_DB_PATH → 库建在该路径、schema 完整、demo 已播种；
2. 父目录（含多层缺失）自动创建；
3. 未设该变量 → 仍解析到项目默认库 data/agriguard.db（默认行为不变）；
4. import 时读取一次的语义（import 后改环境变量不生效）；
5. 优先级：真实环境变量 > .env（load_dotenv(override=False) 语义）。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DEFAULT_DB = ROOT / "data" / "agriguard.db"


def _run_snippet(code: str, env_extra: dict = None, unset: list = None) -> str:
    """在导出 backend 到 PYTHONPATH 的独立子进程里执行 snippet，返回最后一行 stdout。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    for k in unset or []:
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"子进程失败 rc={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    return proc.stdout.strip().splitlines()[-1]


# ---------------------------------------------------------------------------
# 1 + 2. 覆盖生效 + 父目录自动创建 + schema + 播种 demo
# ---------------------------------------------------------------------------
def test_agri_db_path_override_builds_db_and_seeds_demo(tmp_path):
    target = tmp_path / "nested" / "a" / "b" / "ag.db"
    assert not target.parent.exists(), "前置条件：多层父目录应初始不存在"

    code = (
        "import json, sqlite3\n"
        "from app import db\n"
        "from app.services import accounts\n"
        "db.init_db(); accounts.ensure_demo_user()\n"
        "con = sqlite3.connect(str(db.DB_PATH))\n"
        "tables = sorted(r[0] for r in con.execute(\n"
        "    \"select name from sqlite_master where type='table'\"))\n"
        "users = [list(r) for r in con.execute('select username, is_demo from users')]\n"
        "con.close()\n"
        "print(json.dumps({'resolved': str(db.DB_PATH), 'parent': str(db.DATA_DIR),\n"
        "                  'exists': db.DB_PATH.exists(), 'tables': tables, 'users': users}))\n"
    )
    out = json.loads(_run_snippet(code, env_extra={"AGRI_DB_PATH": str(target)}))

    assert Path(out["resolved"]).resolve() == target.resolve(), "库未建在 AGRI_DB_PATH 指定的位置"
    assert out["exists"] is True
    assert target.parent.exists(), "多层缺失的父目录未被自动创建"
    for t in ("users", "sessions", "history"):
        assert t in out["tables"], f"schema 缺少表 {t}：{out['tables']}"
    assert out["users"] == [["demo", 1]], f"demo 账号未按要求播种：{out['users']}"


# ---------------------------------------------------------------------------
# 3. 未设变量 → 默认行为不变
# ---------------------------------------------------------------------------
def test_default_db_path_when_env_absent():
    code = "from app import db\nprint(str(db.DB_PATH))\n"
    out = _run_snippet(code, unset=["AGRI_DB_PATH"])
    assert Path(out).resolve() == DEFAULT_DB.resolve(), (
        f"未设 AGRI_DB_PATH 时应仍用默认库 {DEFAULT_DB}，实得 {out}"
    )


# ---------------------------------------------------------------------------
# 4. import 时读取一次的语义
# ---------------------------------------------------------------------------
def test_db_path_read_once_at_import(tmp_path):
    first = tmp_path / "first.db"
    code = (
        "import json, os\n"
        "from app import db\n"
        "first = str(db.DB_PATH)\n"
        "os.environ['AGRI_DB_PATH'] = 'X:/should_not_apply.db'\n"
        "print(json.dumps({'first': first, 'after': str(db.DB_PATH),\n"
        "                  'unchanged': str(db.DB_PATH) == first}))\n"
    )
    out = json.loads(_run_snippet(code, env_extra={"AGRI_DB_PATH": str(first)}))
    assert Path(out["first"]).resolve() == first.resolve()
    assert out["unchanged"] is True, (
        "import 之后再改 AGRI_DB_PATH 竟改变了 DB_PATH —— 读取一次的语义被破坏"
    )


# ---------------------------------------------------------------------------
# 5. 优先级：真实环境变量 > .env
# ---------------------------------------------------------------------------
def test_config_uses_dotenv_override_false():
    """静态护栏：config.py 必须以 override=False 加载 .env，真实环境变量才能压过它。"""
    src = (BACKEND / "app" / "config.py").read_text(encoding="utf-8")
    assert "load_dotenv(_ENV_FILE, override=False)" in src, (
        "config.py 的 .env 加载未使用 override=False，真实环境变量将无法覆盖 .env"
    )


def test_real_env_overrides_dotenv(tmp_path):
    """真实环境变量优先于 .env（与 config.py 相同的 load_dotenv 语义 + 实际解析器）。"""
    real_db = tmp_path / "real.db"
    dotenv_db = tmp_path / "from_dotenv.db"

    code = (
        "import json, tempfile\n"
        "from pathlib import Path\n"
        "from dotenv import load_dotenv\n"
        "d = Path(tempfile.mkdtemp())\n"
        "env_file = d / '.env'\n"
        f"env_file.write_text('AGRI_DB_PATH={dotenv_db.as_posix()}\\n', encoding='utf-8')\n"
        "load_dotenv(env_file, override=False)   # 与 config.py 完全相同的加载语义\n"
        "from app import db\n"
        "print(str(db.DB_PATH))\n"
    )
    out = _run_snippet(code, env_extra={"AGRI_DB_PATH": str(real_db)})
    assert Path(out).resolve() == real_db.resolve(), (
        f"真实环境变量未压过 .env：DB_PATH={out}（应为 {real_db}）"
    )
