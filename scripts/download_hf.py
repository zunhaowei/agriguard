"""从 HuggingFace 官方镜像下载 PlantVillage 数据集并转为图片目录（train/val）。

使用国内镜像 hf-mirror.com 加速。数据自带 80/20 的 train/test 划分，
test 直接作为验证集 val 使用。

用法（需先 pip install datasets）：
  python scripts/download_hf.py
"""
import os
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "plantvillage"


def main() -> None:
    from datasets import load_dataset

    print("下载数据集 mohanty/PlantVillage (color) ...")
    ds = load_dataset("mohanty/PlantVillage", "color")

    for split, dst_name in [("train", "train"), ("test", "val")]:
        data = ds[split]
        feature = data.features["label"]
        count = 0
        for item in data:
            label_name = feature.int2str(item["label"])
            dst = OUT / dst_name / label_name / f"{split}_{count:06d}.jpg"
            dst.parent.mkdir(parents=True, exist_ok=True)
            item["image"].save(str(dst))
            count += 1
            if count % 5000 == 0:
                print(f"  {dst_name}: 已保存 {count} 张")
        print(f"{dst_name}: 完成，共 {count} 张")

    print("全部完成！数据位于 data/plantvillage")


if __name__ == "__main__":
    main()