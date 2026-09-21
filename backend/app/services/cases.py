"""病例库业务逻辑：作物分组索引、类别详情组装、例图定位。

病例文案**不在这里硬编码** —— 全部来自 `cases_data.py` 这一单点真相（Spec §9）。
本模块只负责分组、拼装响应字段与解析例图文件路径。
"""

from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from .. import cases_data
from ..config import BASE_DIR

# 例图仓库根目录（Spec §9：从已有的测试素材目录读取，不另存副本）。
TEST_ASSETS_DIR: Path = BASE_DIR / "test_assets"


def image_path(class_key: str) -> Optional[Path]:
    """返回该类别的例图绝对路径；不存在返回 None（由路由转 404）。"""
    path = TEST_ASSETS_DIR / cases_data.image_relpath(class_key)
    return path if path.is_file() else None


def crop_index() -> List[dict]:
    """按作物分组的病例库索引（Spec AC-07：14 种作物 / 38 个类别）。"""
    groups: List[dict] = []
    for crop_key in cases_data.CROP_ORDER:
        classes = [c for c in cases_data.CASES if c["crop_key"] == crop_key]
        if not classes:
            continue
        groups.append(
            {
                "crop_key": crop_key,
                "crop_cn": cases_data.CROP_CN[crop_key],
                "count": len(classes),
                "classes": [
                    {
                        "class_key": c["class_key"],
                        "disease_cn": c["disease_cn"],
                        "is_healthy": c["is_healthy"],
                    }
                    for c in classes
                ],
            }
        )
    return groups


def case_detail(class_key: str) -> Optional[dict]:
    """单个病例详情（Spec AC-08：例图 + 中文名 + 简介 + 防治要点）。"""
    case = cases_data.by_key(class_key)
    if case is None:
        return None
    return {
        "ok": True,
        "class_key": case["class_key"],
        "crop_key": case["crop_key"],
        "crop_cn": case["crop_cn"],
        "disease_cn": case["disease_cn"],
        "is_healthy": case["is_healthy"],
        "summary": case["summary"],
        "symptoms": list(case["symptoms"]),
        "prevention": list(case["prevention"]),
        # class_key 含空格与括号（如 Corn_(maize)___Cercospora... Gray_leaf_spot），
        # 必须整体百分号编码，否则前端直接用作 URL 会断链。
        "image_url": f"/api/v1/cases/image/{quote(case['class_key'], safe='')}",
    }
