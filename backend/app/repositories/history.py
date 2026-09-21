"""诊断历史的数据访问。

列表查询刻意**不 select 缩略图 BLOB**（单条 20-40KB，20 条就是近 1MB），
只为 `has_thumb` 判断取一个布尔；缩略图走独立端点按需拉取。
"""

from typing import List, Optional, Tuple

from .. import db

# 列表用字段：不含 BLOB，用 IS NOT NULL 折算 has_thumb
_LIST_FIELDS = (
    "id, created_at, class_key, crop_cn, disease_cn, confidence,"
    " ood_score, is_ood, is_warning, severity_grade, lesion_ratio,"
    " prescription_source,"
    " (thumb_original IS NOT NULL) AS has_thumb"
)


def insert_history(user_id: int, fields: dict, thumb_original, thumb_heatmap) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            "INSERT INTO history ("
            " user_id, created_at, class_key, crop_cn, disease_cn, confidence,"
            " ood_score, is_ood, is_warning, severity_grade, lesion_ratio,"
            " prescription_json, prescription_source, rejected_reason,"
            " thumb_original, thumb_heatmap"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                fields.get("created_at") or db.now_utc(),
                fields.get("class_key"),
                fields.get("crop_cn"),
                fields.get("disease_cn"),
                fields.get("confidence"),
                fields.get("ood_score"),
                1 if fields.get("is_ood") else 0,
                1 if fields.get("is_warning") else 0,
                fields.get("severity_grade"),
                fields.get("lesion_ratio"),
                fields.get("prescription_json"),
                fields.get("prescription_source"),
                fields.get("rejected_reason"),
                thumb_original,
                thumb_heatmap,
            ),
        )
        return int(cur.lastrowid)


def list_history(
    user_id: int, limit: int, offset: int, crop_cn: Optional[str], keyword: Optional[str]
) -> Tuple[int, List[dict]]:
    """返回 `(总数, 当前页记录)`。所有条件都带 user_id，天然完成越权隔离。"""
    where = ["user_id = ?"]
    params: list = [user_id]

    if crop_cn:
        where.append("crop_cn = ?")
        params.append(crop_cn)
    if keyword:
        where.append("(crop_cn LIKE ? OR disease_cn LIKE ? OR class_key LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])

    clause = " WHERE " + " AND ".join(where)

    total_row = db.query_one(f"SELECT COUNT(*) AS n FROM history{clause}", tuple(params))
    total = int(total_row["n"]) if total_row else 0

    rows = db.query_all(
        f"SELECT {_LIST_FIELDS} FROM history{clause}"
        " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        tuple(params + [limit, offset]),
    )
    return total, rows


def get_history(user_id: int, item_id: int) -> Optional[dict]:
    """按 id 取完整记录。user_id 一并入条件 —— 他人记录等同不存在（返回 None）。"""
    return db.query_one(
        "SELECT id, user_id, created_at, class_key, crop_cn, disease_cn, confidence,"
        " ood_score, is_ood, is_warning, severity_grade, lesion_ratio,"
        " prescription_json, prescription_source, rejected_reason,"
        " (thumb_original IS NOT NULL) AS has_original,"
        " (thumb_heatmap IS NOT NULL) AS has_heatmap"
        " FROM history WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )


def get_thumb(user_id: int, item_id: int, kind: str) -> Optional[bytes]:
    column = "thumb_heatmap" if kind == "heatmap" else "thumb_original"
    row = db.query_one(
        f"SELECT {column} AS blob FROM history WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    return row["blob"] if row else None


def delete_history(user_id: int, item_id: int) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            "DELETE FROM history WHERE id = ? AND user_id = ?", (item_id, user_id)
        )
        return cur.rowcount > 0
