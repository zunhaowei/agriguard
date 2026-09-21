"""认证原语：口令散列、会话令牌、Authorization 解析。

【零新依赖】（Spec §3.1 锁定）
不使用 passlib / bcrypt / python-jose / PyJWT，全部用 stdlib 实现：

- 口令：`hashlib.pbkdf2_hmac("sha256", ..., 200000 轮, 16 字节随机 salt)`，
  存 hex。**绝不明文**，且每个用户独立随机 salt（防彩虹表）。
- 比对：`hmac.compare_digest` 常量时间比较（防时序侧信道）。
- 会话：`secrets.token_urlsafe(32)` 作不透明令牌，存 `sessions` 表。
  选数据库会话而非 JWT 的理由：登出可**立即失效**（Spec AC-06），
  且无需引入签名库；代价是一次表查询，单机演示完全可接受。
"""

import hashlib
import hmac
import secrets
from typing import Optional

PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16
SESSION_TTL_DAYS = 7
TOKEN_BYTES = 32


def hash_password(password: str, salt_hex: Optional[str] = None) -> tuple:
    """返回 `(password_hash_hex, salt_hex)`。传 salt_hex 时按既有盐重算（用于校验）。"""
    if salt_hex is None:
        salt = secrets.token_bytes(SALT_BYTES)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt_hex


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    """常量时间校验口令。任何异常（盐格式错误等）一律判为不通过。"""
    try:
        digest, _ = hash_password(password, salt_hex)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(digest, expected_hash or "")


def new_session_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 `Authorization: Bearer <token>` 头中提取令牌；缺失或格式不对返回 None。"""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None
