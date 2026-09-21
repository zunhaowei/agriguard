"""诊断历史业务逻辑：入库（就地生成缩略图）、查询、详情、删除。

【缩略图为什么在这里生成】
`uploads/` 有 24 小时惰性回收策略，热力图与原图过一天就会被删。
因此入库前必须就地把图片压成缩略图 BLOB 一起写进历史表，
否则历史记录里的图明天就变空白（Spec §4 的核心设计决定）。
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from .. import cases_data, imaging
from ..repositories import history as history_repo

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
THUMB_KINDS = ("original", "heatmap")


def _split_name(name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """把「番茄 · 早疫病」拆成 (作物, 病害)；无分隔符时整串作作物名。"""
    if not name:
        return None, None
    if " · " in name:
        crop, disease = name.split(" · ", 1)
        return crop.strip() or None, disease.strip() or None
    return name.strip() or None, None


def save_from_predict(
    user_id: int,
    *,
    class_key: Optional[str] = None,
    name: Optional[str] = None,
    confidence: Optional[float] = None,
    ood_score: Optional[float] = None,
    is_ood: bool = False,
    is_warning: bool = False,
    severity_grade: Optional[str] = None,
    lesion_ratio: Optional[float] = None,
    prescription=None,
    prescription_source: Optional[str] = None,
    original_path: Optional[Path] = None,
    heatmap_path: Optional[Path] = None,
    rejected_reason: Optional[str] = None,
) -> Optional[int]:
    """写入一条历史，返回新记录 id。任何失败由调用方兜底（不影响诊断结果）。"""
    crop_cn, disease_cn = _split_name(name)

    prescription_json = None
    if prescription is not None:
        try:
            data = (
                prescription.model_dump()
                if hasattr(prescription, "model_dump")
                else dict(prescription)
            )
            prescription_json = json.dumps(data, ensure_ascii=False)
        except Exception:
            logger.warning("处方序列化失败，本条历史将不含处方结构", exc_info=True)

    thumb_original = (
        imaging.make_thumbnail_bytes(original_path) if original_path else None
    )
    thumb_heatmap = (
        imaging.make_thumbnail_bytes(heatmap_path) if heatmap_path else None
    )

    return history_repo.insert_history(
        user_id,
        {
            "class_key": class_key,
            "crop_cn": crop_cn,
            "disease_cn": disease_cn,
            "confidence": confidence,
            "ood_score": ood_score,
            "is_ood": is_ood,
            "is_warning": is_warning,
            "severity_grade": severity_grade,
            "lesion_ratio": lesion_ratio,
            "prescription_json": prescription_json,
            "prescription_source": prescription_source,
            "rejected_reason": rejected_reason,
        },
        thumb_original,
        thumb_heatmap,
    )


def save_from_response(
    user_id: int,
    response,
    class_key: Optional[str],
    original_path: Optional[Path],
    heatmap_path: Optional[Path] = None,
) -> Optional[int]:
    """把一次**成功**诊断的响应映射为历史记录并落库。

    由 `/api/v1/predict` 主流程在已登录时调用；未登录不调用（Spec §5.1）。
    """
    top = response.detections[0] if response.detections else None
    return save_from_predict(
        user_id,
        class_key=class_key,
        name=top.name if top else None,
        confidence=top.confidence if top else None,
        ood_score=response.ood_score,
        is_ood=False,
        is_warning=response.warning is not None,
        severity_grade=response.severity_grade,
        lesion_ratio=response.lesion_ratio,
        prescription=response.prescription,
        prescription_source=response.prescription_source,
        original_path=original_path,
        heatmap_path=heatmap_path,
    )


def list_items(
    user_id: int,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    crop: Optional[str] = None,
    keyword: Optional[str] = None,
) -> dict:
    """分页列表（Spec AC-11：按作物筛选 / 关键词搜索只返回匹配项）。"""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    # 先 strip 再判空：' ' / '  ' 这类纯空白必须与"未提供"同义。
    # 此前把 strip 前的原值当成有效值传下去，' ' 会退化成""进而被数据层视为
    # "不过滤"——用户以为筛过了、实际拿到全量数据（与下面的注释意图相反）。
    crop_arg = (crop or "").strip()
    if not crop_arg:
        crop_cn = None
    else:
        # 已 strip 的非空值若无法解析成作物名，**不能退化成"不过滤"**：
        # 保留原值参与等值匹配，自然得到空结果（宁可不匹配，也不能假装筛过了）。
        crop_cn = cases_data.crop_cn_by_value(crop_arg) or crop_arg

    # q 同理：strip 后为空即"未提供"。注意 strip 与判空必须同时做，
    # 否则 ' ' 会被当成有效关键词去 LIKE '%%%'，效果等同不过滤。
    keyword = (keyword or "").strip() or None

    total, rows = history_repo.list_history(user_id, limit, offset, crop_cn, keyword)
    return {"ok": True, "total": total, "items": [_brief(row) for row in rows]}


def _brief(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "created_at": row["created_at"],
        "crop_cn": row["crop_cn"],
        "disease_cn": row["disease_cn"],
        "confidence": row["confidence"],
        "severity_grade": row["severity_grade"],
        "has_thumb": bool(row["has_thumb"]),
        "is_ood": bool(row["is_ood"]),
    }


def get_item(user_id: int, item_id: int) -> Optional[dict]:
    """历史详情（Spec AC-13：他人记录返回 None，路由据此转 404）。"""
    row = history_repo.get_history(user_id, item_id)
    if row is None:
        return None

    prescription = None
    if row["prescription_json"]:
        try:
            prescription = json.loads(row["prescription_json"])
        except (TypeError, ValueError):
            logger.warning("历史 %s 的处方 JSON 解析失败，按无处方返回", item_id)

    return {
        "ok": True,
        "item": {
            "id": int(row["id"]),
            "created_at": row["created_at"],
            "class_key": row["class_key"],
            "crop_cn": row["crop_cn"],
            "disease_cn": row["disease_cn"],
            "confidence": row["confidence"],
            "ood_score": row["ood_score"],
            "is_ood": bool(row["is_ood"]),
            "is_warning": bool(row["is_warning"]),
            "severity_grade": row["severity_grade"],
            "lesion_ratio": row["lesion_ratio"],
            "prescription": prescription,
            "prescription_source": row["prescription_source"],
            "rejected_reason": row["rejected_reason"],
            "has_thumb": bool(row["has_original"]),
        },
    }


def get_thumb(user_id: int, item_id: int, kind: str) -> Optional[bytes]:
    if kind not in THUMB_KINDS:
        kind = "original"
    return history_repo.get_thumb(user_id, item_id, kind)


def delete_item(user_id: int, item_id: int) -> bool:
    return history_repo.delete_history(user_id, item_id)


def create_manual(user_id: int, payload: dict) -> int:
    """手动补录一条历史（Spec §5 可选端点；不携带图片，缩略图为空）。"""
    return save_from_predict(
        user_id,
        class_key=payload.get("class_key"),
        name=payload.get("name")
        or (
            f"{payload.get('crop_cn')} · {payload.get('disease_cn')}"
            if payload.get("crop_cn") and payload.get("disease_cn")
            else payload.get("crop_cn") or payload.get("disease_cn")
        ),
        confidence=payload.get("confidence"),
        ood_score=payload.get("ood_score"),
        is_ood=bool(payload.get("is_ood")),
        is_warning=bool(payload.get("is_warning")),
        severity_grade=payload.get("severity_grade"),
        lesion_ratio=payload.get("lesion_ratio"),
        prescription=payload.get("prescription"),
        prescription_source=payload.get("prescription_source"),
    )
