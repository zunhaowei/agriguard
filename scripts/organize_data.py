"""把解压后的 PlantVillage color 图片整理为 ultralytics 分类训练所需的 train/val 结构。

数据源：data/pv_raw/raw/color/<类别>/...  (38 类)
输出：  data/plantvillage/{train,val}/<类别>/...
使用 move（同盘重命名），速度快且不额外占磁盘。

用法：
  python scripts/organize_data.py --split 0.8
"""
import argparse
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "pv_raw"
OUT = ROOT / "data" / "plantvillage"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def find_color() -> Path | None:
    for p in RAW.rglob("*"):
        if p.is_dir() and p.name == "color":
            return p
    return None


def main(split: float, seed: int) -> None:
    color = find_color()
    if color is None:
        raise SystemExit(f"未在 {RAW} 下找到 color 目录，请确认数据集已解压。")
    classes = sorted(d for d in color.iterdir() if d.is_dir())
    if not classes:
        raise SystemExit("color 目录下没有类别文件夹。")
    random.seed(seed)
    total_train = total_val = 0
    for cls in classes:
        imgs = [f for f in cls.iterdir() if f.suffix in IMG_EXTS]
        random.shuffle(imgs)
        n_train = max(1, int(len(imgs) * split))
        for f in imgs[:n_train]:
            dst = OUT / "train" / cls.name / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dst))
            total_train += 1
        for f in imgs[n_train:]:
            dst = OUT / "val" / cls.name / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dst))
            total_val += 1
    print(f"整理完成：类别 {len(classes)} 个，训练集 {total_train} 张，验证集 {total_val} 张")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    main(args.split, args.seed)