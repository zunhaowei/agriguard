"""病例库路由：索引 / 详情 / 例图（Spec §5，均可匿名访问）。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..schemas import CaseDetailResponse, CasesIndexResponse
from ..services import cases as cases_service

router = APIRouter(prefix="/api/v1/cases", tags=["病例库"])


@router.get("", response_model=CasesIndexResponse)
def index() -> dict:
    """全部作物与类别索引（Spec AC-07）。"""
    return {"ok": True, "crops": cases_service.crop_index()}


# 注意：/image/{class_key} 必须在 /{class_key} 之前声明，
# 否则 "image" 会被当作 class_key 匹配到详情路由。
@router.get("/image/{class_key}")
def image(class_key: str) -> Response:
    """病例例图（Spec：返回 image/jpeg）。"""
    path = cases_service.image_path(class_key)
    if path is None:
        raise HTTPException(status_code=404, detail="未找到该病例的例图。")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.get("/{class_key}", response_model=CaseDetailResponse)
def detail(class_key: str) -> dict:
    """单个病例详情（Spec AC-08）。"""
    data = cases_service.case_detail(class_key)
    if data is None:
        raise HTTPException(status_code=404, detail="未收录该病例。")
    return data
