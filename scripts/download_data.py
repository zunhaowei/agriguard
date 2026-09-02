"""下载 PlantVillage 数据集并组织为图像分类目录结构。

数据来源（任选其一）：
1. Roboflow（推荐，需要 API Key，见 https://roboflow.com）
   ROBODL_API_KEY=xxx python scripts/download_data.py --source roboflow
2. 手动下载 Kaggle 数据集「emmarex/plantdisease」，解压到 data/raw/

组织后的目录结构（可直接用于 ultralytics 分类训练）：
data/plantvillage/
  train/
    Apple___Apple_scab/ *.jpg
    Apple___healthy/      *.jpg
    ...
  val/
    ...
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "plantvillage"


def download_roboflow(api_key: str):
    from roboflow import Roboflow

    rf = Roboflow(api_key=api_key)
    project = rf.workspace("plantvillage-dataset").project("plantvillage")
    dataset = project.version(1).download("folder")
    src = Path(dataset.location)
    shutil.copytree(src / "train", OUT / "train", dirs_exist_ok=True)
    shutil.copytree(src / "valid", OUT / "val", dirs_exist_ok=True)
    print("下载完成：", OUT)


def organize_from_raw():
    # 若已手动解压到 data/raw，按类别文件夹整理为 train/val
    if not RAW.exists():
        print("未找到 data/raw 目录，请先下载数据集或使用 --source roboflow")
        return
    print("TODO: 根据实际解压结构实现 train/val 划分")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["roboflow", "raw"], default="raw")
    args = parser.parse_args()
    if args.source == "roboflow":
        import os

        download_roboflow(os.environ["ROBODL_API_KEY"])
    else:
        organize_from_raw()