"""账号业务逻辑：注册、登录、登出、会话校验、演示账号播种。

【安全要点】
- 口令校验失败一律返回同一句「用户名或密码错误」，**不区分**用户不存在与密码
  错误（Spec AC-04），避免账号存在性泄露。
- 会话过期即刻删除并视为未登录（Spec AC-05）；登出删除会话行，令牌立即失效
  （Spec AC-06），这也是选择数据库会话而非 JWT 的原因。
"""

import logging
import re
from typing import Optional

from .. import db, security
from ..repositories import users as users_repo

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 64
DISPLAY_NAME_MAX_LEN = 32

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"
DEMO_DISPLAY_NAME = "演示账号"


class AuthError(Exception):
    """业务校验失败：status 直接映射 HTTP 状态码，reason 面向用户可读。"""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def public_user(row: dict) -> dict:
    """把用户行裁剪为可对外字段（绝不带出 password_hash / salt）。"""
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "display_name": (row.get("display_name") or "").strip() or row["username"],
        "is_demo": bool(row["is_demo"]),
    }


def _issue_token(user_id: int) -> str:
    token = security.new_session_token()
    users_repo.create_session(token, user_id, security.SESSION_TTL_DAYS)
    return token


def register(username: str, password: str, display_name: Optional[str] = None) -> dict:
    """注册并直接登录（Spec AC-01）。用户名占用返回 409（Spec AC-02）。"""
    username = (username or "").strip()
    if not USERNAME_RE.match(username):
        raise AuthError(400, "用户名需为 3-20 位字母、数字或下划线。")
    if not isinstance(password, str) or not (
        PASSWORD_MIN_LEN <= len(password) <= PASSWORD_MAX_LEN
    ):
        raise AuthError(400, f"密码长度需为 {PASSWORD_MIN_LEN}-{PASSWORD_MAX_LEN} 位。")

    name = (display_name or "").strip()[:DISPLAY_NAME_MAX_LEN] or username
    pw_hash, salt = security.hash_password(password)
    user_id = users_repo.create_user(username, name, pw_hash, salt, is_demo=False)
    if user_id is None:
        raise AuthError(409, "该用户名已被占用，请更换后重试。")

    row = users_repo.get_by_id(user_id) or {"id": user_id, "username": username,
                                            "display_name": name, "is_demo": 0}
    return {"ok": True, "token": _issue_token(user_id), "user": public_user(row)}


def login(username: str, password: str) -> dict:
    row = users_repo.get_by_username((username or "").strip())
    if row is None or not security.verify_password(
        password or "", row["salt"], row["password_hash"]
    ):
        raise AuthError(401, "用户名或密码错误。")
    return {"ok": True, "token": _issue_token(int(row["id"])), "user": public_user(row)}


def logout(token: Optional[str]) -> None:
    if token:
        users_repo.delete_session(token)


def user_from_token(token: Optional[str]) -> Optional[dict]:
    """校验会话令牌；有效且未过期返回用户公开信息，否则返回 None。"""
    if not token:
        return None
    row = users_repo.get_session_user(token)
    if row is None:
        return None
    if db.is_expired(row["expires_at"]):
        users_repo.delete_session(token)
        return None
    return public_user(row)


def ensure_demo_user() -> None:
    """幂等播种演示账号 demo/demo1234（is_demo=1），仅首次建库时写入。"""
    if users_repo.get_by_username(DEMO_USERNAME) is None:
        pw_hash, salt = security.hash_password(DEMO_PASSWORD)
        users_repo.create_user(
            DEMO_USERNAME, DEMO_DISPLAY_NAME, pw_hash, salt, is_demo=True
        )
        logger.info("已播种演示账号：%s", DEMO_USERNAME)
    try:
        removed = users_repo.delete_expired_sessions()
        if removed:
            logger.info("启动清理过期会话 %d 条", removed)
    except Exception:  # pragma: no cover - 清理属辅助动作，绝不阻断启动
        logger.debug("清理过期会话失败（忽略）", exc_info=True)
