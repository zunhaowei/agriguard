"""FastAPI 认证依赖。

- `require_user`：强制登录，未登录/令牌无效/已过期一律 401（Spec AC-05）。
- `optional_user`：可选登录，供 `/api/v1/predict` 使用 —— 带有效令牌则自动入库，
  不带或令牌无效则照常诊断、只是不落库（Spec §5.1，保证向后兼容）。
"""

from typing import Optional

from fastapi import Header, HTTPException

from .. import security
from ..services import accounts


def _resolve(authorization: Optional[str]) -> Optional[dict]:
    return accounts.user_from_token(security.bearer_token(authorization))


def token_of(authorization: Optional[str]) -> Optional[str]:
    return security.bearer_token(authorization)


def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
    user = _resolve(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或登录状态已过期，请先登录。")
    return user


def optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    return _resolve(authorization)
