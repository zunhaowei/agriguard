"""用户与会话的数据访问。

仅负责 SQL 搬运；口令散列、令牌生成、过期判断等策略由 service / security 决定。
"""

import sqlite3
from typing import Optional

from .. import db


def create_user(
    username: str,
    display_name: str,
    password_hash: str,
    salt: str,
    is_demo: bool = False,
    created_at: Optional[str] = None,
) -> Optional[int]:
    """插入用户。

    返回新用户 id；**仅当用户名（NOCASE UNIQUE）冲突时**返回 None，
    其余完整性错误一律继续上抛（由统一错误处理返回 500 并记录原始错误）。
    —— 否则任何别的约束失败（非空约束、将来新增的唯一索引……）都会被
    错误地报成「用户名已被占用」，把排障方向带偏。

    冲突判定刻意**不解析 SQLite 的错误文本**（形如
    `UNIQUE constraint failed: users.username` 的字符串会随版本/本地化变化，
    且用字符串驱动业务逻辑本身脆弱）：唯一约束冲突时同名行必然已存在，
    回查一次即可确证；回查不到，说明是别的完整性错误，原样抛出。
    """
    try:
        with db.cursor() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, salt, is_demo, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    username,
                    display_name,
                    password_hash,
                    salt,
                    1 if is_demo else 0,
                    created_at or db.now_utc(),
                ),
            )
            return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        if db.query_one("SELECT 1 AS hit FROM users WHERE username = ?", (username,)):
            return None
        raise


# 对外暴露的用户字段白名单：绝不把 password_hash / salt 带出数据层。
_PUBLIC_FIELDS = "id, username, display_name, is_demo"


def get_by_username(username: str) -> Optional[dict]:
    """按用户名查询（含口令字段，仅供 service 校验使用）。"""
    return db.query_one(
        "SELECT id, username, display_name, password_hash, salt, is_demo, created_at"
        " FROM users WHERE username = ?",
        (username,),
    )


def get_by_id(user_id: int) -> Optional[dict]:
    return db.query_one(f"SELECT {_PUBLIC_FIELDS} FROM users WHERE id = ?", (user_id,))


def create_session(token: str, user_id: int, ttl_days: int) -> None:
    with db.cursor() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, db.now_utc(), db.iso_in(ttl_days)),
        )


def get_session_user(token: str) -> Optional[dict]:
    """按令牌取用户（联表，一次查询拿到过期时间与用户公开信息）。"""
    return db.query_one(
        "SELECT s.token AS token, s.expires_at AS expires_at,"
        " u.id AS id, u.username AS username, u.display_name AS display_name, u.is_demo AS is_demo"
        " FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,),
    )


def delete_session(token: str) -> int:
    with db.cursor() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return cur.rowcount


def delete_expired_sessions() -> int:
    """清理已过期会话（顺手做，避免 sessions 表无限增长）。"""
    with db.cursor() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE expires_at <= ?", (db.now_utc(),)
        )
        return cur.rowcount
