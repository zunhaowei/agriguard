"""SQLite 数据访问底座：连接管理、建表、时间与查询小工具。

【为什么用 stdlib sqlite3 而不是 ORM】（Spec §3 技术选型，锁定）
本项目依赖纪律严格（`ultralytics` 已锁死 8.4.137），每引入一个第三方库都会
抬高"换机器复现"的风险；而本次只有 3 张表、单机演示、单用户 < 1000 条记录，
ORM 的收益远小于风险。故全程只用 `sqlite3`。
认证相关（口令散列、会话令牌）同样只用 stdlib，见 security.py。

【库文件放在哪里】
默认 `data/agriguard.db`：`.gitignore` 用 `data/*` 排除了该目录，因此演示数据与
用户数据都不会被提交。可用环境变量 `AGRI_DB_PATH` 覆盖（见下方常量区）。

【并发模型】
FastAPI 把同步端点派发到 anyio 线程池，故连接以 `check_same_thread=False`
创建，并用模块级可重入锁把每次读写串行化 —— 单机演示的量级下这比连接池
更简单也更不容易出错。
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from .config import BASE_DIR

# ---------------------------------------------------------------------------
# 库文件位置：默认沿用历史路径，可通过环境变量覆盖
# ---------------------------------------------------------------------------
# 覆盖入口：`AGRI_DB_PATH`（命名沿用本项目既有的 `AGRI_PYTHON` 风格）。
#
# 为什么需要它：库路径此前是模块级常量、产品代码没有正式入口，导致测试只能
# monkeypatch 模块全局并手工复位连接缓存 —— 依赖内部实现细节，很脆弱。
# 有了这个入口，测试/多环境只要设一个环境变量即可各用各的库。
#
# 优先级：**真实环境变量 > .env 文件**。config.py 用
# `load_dotenv(override=False)` 加载 .env，因此已存在的真实环境变量不会被
# .env 覆盖，符合 12-factor 惯例（CI / 演示机可临时指定而不改文件）。
#
# 相对路径按「当前工作目录」解析；路径中的 `~` 会展开。
DB_PATH_ENV = "AGRI_DB_PATH"


def _resolve_db_location() -> Tuple[Path, Path]:
    """返回 `(库文件所在目录, 库文件路径)`。

    - **未设置** `AGRI_DB_PATH`：`data/agriguard.db`，与历史行为完全一致。
    - **已设置**：使用该路径；父目录不存在时由 `_connect()` 自动创建
      （含多层缺失的父目录 —— 本项目历史上踩过"目录不存在导致应用起不来"的坑）。
    """
    raw = (os.getenv(DB_PATH_ENV) or "").strip()
    if raw:
        path = Path(raw).expanduser()
        return path.parent, path
    default_dir = BASE_DIR / "data"
    return default_dir, default_dir / "agriguard.db"


DATA_DIR, DB_PATH = _resolve_db_location()

# 表结构（Spec §4 锁定，逐字实现，不得增删字段语义）。
# 缩略图刻意存 BLOB 而不是文件：uploads/ 有 24 小时惰性回收策略，
# 若存文件，历史记录过一天就会变成空白。
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    display_name  TEXT    NOT NULL DEFAULT '',
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at          TEXT NOT NULL,
    class_key           TEXT,
    crop_cn             TEXT,
    disease_cn          TEXT,
    confidence          REAL,
    ood_score           REAL,
    is_ood              INTEGER NOT NULL DEFAULT 0,
    is_warning          INTEGER NOT NULL DEFAULT 0,
    severity_grade      TEXT,
    lesion_ratio        REAL,
    prescription_json   TEXT,
    prescription_source TEXT,
    rejected_reason     TEXT,
    thumb_original      BLOB,
    thumb_heatmap       BLOB
);
CREATE INDEX IF NOT EXISTS idx_history_user_time ON history(user_id, created_at DESC);
"""

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None


# ---------------------------------------------------------------------------
# 时间工具（统一 UTC / ISO8601，保证同一格式下字符串可直接比较）
# ---------------------------------------------------------------------------
def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iso_in(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


def is_expired(expires_at: str) -> bool:
    """判断会话是否过期。无法解析的脏值一律视为已过期（宁严勿松）。"""
    try:
        return datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True


# ---------------------------------------------------------------------------
# 连接与游标
# ---------------------------------------------------------------------------
def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        # parents=True：AGRI_DB_PATH 指向的父目录（可能多层缺失）也在这里一并建好，
        # 不会因为目录不存在而连接失败。
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            # WAL 在个别文件系统上可能不可用；退回默认日志模式即可，不影响功能。
            pass
        _conn = conn
    return _conn


@contextmanager
def cursor() -> Iterator[sqlite3.Connection]:
    """串行化的写事务上下文：正常退出提交，异常回滚，锁保证线程安全。"""
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def query_all(sql: str, params: tuple = ()) -> List[dict]:
    with cursor() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    with cursor() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None


def execute(sql: str, params: tuple = ()) -> int:
    """执行写语句，返回 lastrowid（不适用时返回受影响行数）。"""
    with cursor() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid) if cur.lastrowid is not None else cur.rowcount


def init_db() -> None:
    """幂等建表。由应用启动钩子调用，可重复执行。"""
    with cursor() as conn:
        conn.executescript(SCHEMA_SQL)
