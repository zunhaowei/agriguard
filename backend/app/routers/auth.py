"""认证路由：注册 / 登录 / 登出 / 当前用户（Spec §5）。"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from ..schemas import AuthResponse, LoginRequest, MeResponse, OkResponse, RegisterRequest
from ..services import accounts
from .deps import require_user, token_of

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> dict:
    """注册并直接登录（Spec AC-01/AC-02）。"""
    try:
        return accounts.register(payload.username, payload.password, payload.display_name)
    except accounts.AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.reason) from exc


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> dict:
    """登录（Spec AC-03/AC-04）。"""
    try:
        return accounts.login(payload.username, payload.password)
    except accounts.AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.reason) from exc


@router.post("/logout", response_model=OkResponse)
def logout(
    authorization: Optional[str] = Header(default=None),
    user: dict = Depends(require_user),
) -> dict:
    """登出：删除会话行，令牌立即失效（Spec AC-06）。"""
    accounts.logout(token_of(authorization))
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: dict = Depends(require_user)) -> dict:
    return {"ok": True, "user": user}
