"""解压并整理下载的病叶数据集，组织成 ultralytics 分类训练格式。

输入：data/downloads/*.zip（由 download_extra_datasets.py 下载）
输出：data/plantvillage_combined/{train,val}/<类别>/<图片>

逻辑：
1. 解压每个 zip 到 data/datasets_raw/<名>/；
2. 递归扫描「包含图片文件的叶子目录」，将其视为一个「类别」；
3. 把所有类别图片合并，按 8:2 划分 train/val；
4. 输出到 data/plantvillage_combined/，可直接用于 ultralytics 训练。

用法：
  python scripts/organize_extra_data.py --split 0.8
"""
import argparse
import random
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DL_DIR = ROOT / "data" / "downloads"
RAW_DIR = ROOT / "data" / "datasets_raw"
OUT_DIR = ROOT / "data" / "plantvillage_combined"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def extract_all():
    """解压 downloads 下所有 zip 到 datasets_raw。"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for zf in sorted(DL_DIR.glob("*.zip")):
        dest = RAW_DIR / zf.stem
        if dest.exists() and any(dest.rglob("*")):
            print(f"[skip] 已解压：{zf.name}", flush=True)
            continue
        print(f"[extract] {zf.name} -> {dest}", flush=True)
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zf) as z:
            z.extractall(dest)
    print("解压完成。", flush=True)


def find_class_dirs(root: Path):
    """递归找「直接包含图片文件的目录」，作为类别文件夹。

    返回 {类名: [图片Path列表]}。类名取目录名（去重时同名合并）。
    """
    classes: dict[str, list[Path]] = {}
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        imgs = [f for f in d.iterdir() if f.suffix in IMG_EXTS]
        if not imgs:
            continue
        # 跳过明显的非类别目录（如 zip 顶层空壳）
        name = d.name
        classes.setdefault(name, []).extend(imgs)
    return classes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    extract_all()

    # 汇总所有类别
    all_classes: dict[str, list[Path]] = {}
    for raw_root in RAW_DIR.iterdir():
        if not raw_root.is_dir():
            continue
        classes = find_class_dirs(raw_root)
        for name, imgs in classes.items():
            all_classes.setdefault(name, []).extend(imgs)

    if not all_classes:
        raise SystemExit("未找到任何类别文件夹，请检查 data/datasets_raw 结构。")

    print(f"\n共发现 {len(all_classes)} 个类别：")
    for name, imgs in sorted(all_classes.items()):
        print(f"  {name}: {len(imgs)} 张")

    random.seed(args.seed)
    total_train = total_val = 0
    # 清理旧输出（避免重复累积）
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    for name, imgs in all_classes.items():
        # 去重（同路径去重；不同来源同名文件按内容不重复处理，保留）
        unique = list(dict.fromkeys(imgs))
        random.shuffle(unique)
        n_train = max(1, int(len(unique) * args.split))
        for f in unique[:n_train]:
            dst = OUT_DIR / "train" / name / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            total_train += 1
        for f in unique[n_train:]:
            dst = OUT_DIR / "val" / name / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            total_val += 1

    print(f"\n整理完成：{len(all_classes)} 类，train {total_train} 张，val {total_val} 张。")
    print(f"输出目录：{OUT_DIR}")


if __name__ == "__main__":
    main()
