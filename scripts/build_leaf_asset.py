"""生成演示物料用的高清病叶素材：media/gen/leaf_disease_hi.jpg

【为什么需要这个脚本】
`media/` 目录历史上丢失过一次，而 `scripts/regenerate_heatmap.py`、
`build_video2.py`、`build_poster.py` 都以 `media/gen/leaf_disease_hi.jpg` 为输入。
本脚本把这张「高清病叶」的生成过程固化为可复现步骤，避免再次丢失后无从重建。

【素材来源与选择理由】
源图取本项目训练数据 `test_assets/supported_diseased/` 中的真实病叶样本。
- 为什么不用网上找的田间照片：**产品本身就要求「单片叶 + 纯色背景」的拍摄方式**，
  用田间成片病株做门面反而与实际能力不符；而 PlantVillage 风格的单叶照片
  恰好就是产品设计上要处理的那类输入，视觉与产品能力一致。
- 版权上无第三方约束（属于本项目自有的训练数据）。

【分辨率说明（如实记录）】
PlantVillage 原始图像为 256x256。本脚本放大到 1920x1920。
在成品中的实际显示尺寸：
    - 海报：卡片最终约 220px（源图 256px 已足够，**无可见损失**）
    - 视频：卡片 230/300px，结果展示区约 600px（放大会略软，视频场景下可接受）
因此这是一张「够用且口径一致」的素材，不是印刷级摄影图。若日后需要更高清，
应改用团队自拍或采购授权的单叶实拍照片替换本文件，其余流程无需改动。

用法：
    .venv\\Scripts\\python.exe scripts\\build_leaf_asset.py
    .venv\\Scripts\\python.exe scripts\\build_leaf_asset.py --source <图片路径>
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "media" / "gen"
TARGET = 1920

# 默认源：番茄早疫病，病斑边界清晰、叶色对比明显，适合作为门面素材
DEFAULT_SOURCE = ROOT / "test_assets" / "supported_diseased" / "Tomato__Early_blight.jpg"


def leaf_bbox(img_bgr: np.ndarray) -> tuple:
    """用 HSV 绿色掩膜估出叶片外接框（PlantVillage 叶片居中且背景近纯色）。"""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([20, 30, 30]), np.array([105, 255, 255]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        h, w = img_bgr.shape[:2]
        return 0, 0, w, h
    all_pts = np.vstack([c.reshape(-1, 2) for c in cnts])
    x, y, w, h = cv2.boundingRect(all_pts)
    return x, y, w, h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(DEFAULT_SOURCE), help="源病叶图片路径")
    ap.add_argument("--size", type=int, default=TARGET, help="输出边长，默认 1920")
    ap.add_argument("--margin", type=float, default=0.10, help="叶片外扩留白比例")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"[错误] 源图不存在：{src}")
        return 1

    img = cv2.imread(str(src))
    if img is None:
        print(f"[错误] 无法读取：{src}")
        return 1
    h, w = img.shape[:2]

    # 裁到叶片外接框 + 留白，再补成正方形，保证放大后不变形
    x, y, bw, bh = leaf_bbox(img)
    m = int(max(bw, bh) * args.margin)
    x0, y0 = max(0, x - m), max(0, y - m)
    x1, y1 = min(w, x + bw + m), min(h, y + bh + m)
    crop = img[y0:y1, x0:x1]

    ch, cw = crop.shape[:2]
    side = max(ch, cw)
    pad_v, pad_h = side - ch, side - cw
    crop = cv2.copyMakeBorder(
        crop, pad_v // 2, pad_v - pad_v // 2, pad_h // 2, pad_h - pad_h // 2,
        cv2.BORDER_REPLICATE,
    )

    pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    up = pil.resize((args.size, args.size), Image.LANCZOS)
    # 上采样后轻微锐化，补偿插值带来的边缘软化
    up = up.filter(ImageFilter.UnsharpMask(radius=3, percent=80, threshold=3))

    GEN.mkdir(parents=True, exist_ok=True)
    out = GEN / "leaf_disease_hi.jpg"
    up.save(out, quality=96, subsampling=0)
    print(f"源图      : {src}  ({w}x{h})")
    print(f"叶片外接框: x={x} y={y} w={bw} h={bh}")
    print(f"输出      : {out}  {up.size}  {out.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
