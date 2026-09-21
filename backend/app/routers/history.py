"""历史记录路由：列表 / 详情 / 缩略图 / 删除 / 手动补录（Spec §5）。

全部端点强制登录；所有查询都带 user_id ——
访问他人记录等同「不存在」，统一返回 404 而不返回 403（Spec AC-13，
避免通过状态码差异探测某条 id 是否真实存在）。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..schemas import (
    HistoryCreateRequest,
    HistoryCreateResponse,
    HistoryDetailResponse,
    HistoryListResponse,
    OkResponse,
)
from ..services import history as history_service
from .deps import require_user

router = APIRouter(prefix="/api/v1/history", tags=["历史记录"])


@router.get("", response_model=HistoryListResponse)
def list_history(
    limit: int = 20,
    offset: int = 0,
    crop: Optional[str] = None,
    q: Optional[str] = None,
    user: dict = Depends(require_user),
) -> dict:
    return history_service.list_items(user["id"], limit, offset, crop, q)


@router.post("", response_model=HistoryCreateResponse)
def create_history(
    payload: HistoryCreateRequest, user: dict = Depends(require_user)
) -> dict:
    new_id = history_service.create_manual(user["id"], payload.model_dump())
    return {"ok": True, "id": new_id}


@router.get("/{item_id}", response_model=HistoryDetailResponse)
def get_history(item_id: int, user: dict = Depends(require_user)) -> dict:
    data = history_service.get_item(user["id"], item_id)
    if data is None:
        raise HTTPException(status_code=404, detail="未找到该条历史记录。")
    return data


@router.get("/{item_id}/thumb")
def get_thumb(
    item_id: int, kind: str = "original", user: dict = Depends(require_user)
) -> Response:
    blob = history_service.get_thumb(user["id"], item_id, kind)
    if not blob:
        raise HTTPException(status_code=404, detail="未找到该缩略图。")
    return Response(content=blob, media_type="image/jpeg")


@router.delete("/{item_id}", response_model=OkResponse)
def delete_history(item_id: int, user: dict = Depends(require_user)) -> dict:
    if not history_service.delete_item(user["id"], item_id):
        raise HTTPException(status_code=404, detail="未找到该条历史记录。")
    return {"ok": True}
