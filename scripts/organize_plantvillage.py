"""整理下载的 PlantVillage 增强版数据集，输出 ultralytics 分类格式（train/val）。

处理要点：
1. extractall 解压增强版（C 实现，幂等续跑）；
2. 排除「Background_without_leaves」背景类；
3. 类别名归一化：Kaggle 版命名对齐到本项目 detector.py 的 PlantVillage 原始命名；
4. 用 shutil.move（同盘 rename，快）把类别目录移入输出目录，避免二次复制 IO；
5. 按 8:2 从 train 划出 val。

输出：data/plantvillage/{train,val}/<类别>/<图片>

用法：
  python scripts/organize_plantvillage.py
"""
import random
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DL_DIR = ROOT / "data" / "downloads"
TMP_DIR = ROOT / "data" / "datasets_raw" / "aug"
OUT_DIR = ROOT / "data" / "plantvillage"

AUG_ZIP = DL_DIR / "plantvillage_augmentation.zip"

IMG_EXTS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
SKIP_CLASS = "Background_without_leaves"

RENAME = {
    "Cherry___healthy": "Cherry_(including_sour)___healthy",
    "Cherry___Powdery_mildew": "Cherry_(including_sour)___Powdery_mildew",
    "Corn___Cercospora_leaf_spot Gray_leaf_spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___Common_rust": "Corn_(maize)___Common_rust_",
    "Corn___Northern_Leaf_Blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn___healthy": "Corn_(maize)___healthy",
}


def extract_aug():
    """解压增强版到 TMP_DIR，逐文件跳过已解压部分（幂等续跑）。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    done = 0
    skip = 0
    with zipfile.ZipFile(AUG_ZIP) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        total = len(members)
        for m in members:
            target = TMP_DIR / m.filename
            if target.exists() and target.stat().st_size == m.file_size:
                skip += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
            done += 1
            if done % 5000 == 0:
                print(f"  解压进度：新增 {done}，跳过 {skip} / 总 {total}", flush=True)
    print(f"解压完成：新增 {done}，跳过已存在 {skip}。", flush=True)


def organize():
    """把 TMP_DIR 下的类别目录 move 到 OUT_DIR/train（归一化类名）。"""
    # 找到解压后的顶层包装目录（如 Plant_leave_diseases_dataset_with_augmentation）
    src_root = None
    for d in TMP_DIR.iterdir():
        if d.is_dir() and any(f.suffix in IMG_EXTS for sub in d.iterdir() for f in (sub.iterdir() if sub.is_dir() else [])):
            src_root = d
            break
    if src_root is None:
        src_root = TMP_DIR

    train_root = OUT_DIR / "train"
    train_root.mkdir(parents=True, exist_ok=True)
    counts = {}
    for cd in sorted(src_root.iterdir()):
        if not cd.is_dir():
            continue
        cls = cd.name
        if cls == SKIP_CLASS:
            continue
        cls_norm = RENAME.get(cls, cls)
        dst = train_root / cls_norm
        # move 类别目录（同盘 rename，快）
        if dst.exists():
            # 已存在则逐文件移动
            for f in cd.iterdir():
                if f.suffix in IMG_EXTS:
                    shutil.move(str(f), str(dst / f.name))
            # 清理空目录
            try:
                cd.rmdir()
            except OSError:
                pass
        else:
            shutil.move(str(cd), str(dst))
        n = len([f for f in dst.iterdir() if f.suffix in IMG_EXTS])
        counts[cls_norm] = n
    return counts


def split_val(val_ratio=0.2, seed=42):
    """从 train 每类随机 move val_ratio 比例到 val。"""
    train_root = OUT_DIR / "train"
    val_root = OUT_DIR / "val"
    val_root.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    val_counts = {}
    for cd in sorted(train_root.iterdir()):
        if not cd.is_dir():
            continue
        imgs = [f for f in cd.iterdir() if f.suffix in IMG_EXTS]
        random.shuffle(imgs)
        n_val = max(1, int(len(imgs) * val_ratio)) if len(imgs) > 1 else 0
        dst = val_root / cd.name
        dst.mkdir(parents=True, exist_ok=True)
        for f in imgs[:n_val]:
            shutil.move(str(f), str(dst / f.name))
        val_counts[cd.name] = n_val
    return val_counts


def main():
    extract_aug()
    print("整理类别目录 -> train ...", flush=True)
    counts = organize()
    print(f"train 整理完成：{len(counts)} 类", flush=True)

    print("划分 val（20%）...", flush=True)
    val_counts = split_val()
    print(f"val 划分完成：{len(val_counts)} 类", flush=True)

    # 统计最终结果
    print("\n=== 各类别分布（train / val）===")
    for cls in sorted(counts):
        tv = counts[cls] - val_counts.get(cls, 0)
        vv = val_counts.get(cls, 0)
        print(f"  {cls}: train {tv} / val {vv}")

    total_train = sum(counts[c] - val_counts.get(c, 0) for c in counts)
    total_val = sum(val_counts.values())
    print(f"\n整理完成：{len(counts)} 类，train {total_train} 张，val {total_val} 张。")
    print(f"输出目录：{OUT_DIR}")


if __name__ == "__main__":
    main()
