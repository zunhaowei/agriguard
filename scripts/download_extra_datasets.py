"""从魔搭（ModelScope，国内 CDN）下载病叶训练数据集到 data/ 目录。

数据源均为公开数据集，通过 modelscope 的 resolve URL 直接下载，支持断点续传。

下载清单：
1. OmniData/PlantVillage — Plant_leaf_diseases_dataset_with_augmentation.zip（增强版，约 949MB）
2. OmniData/PlantVillage — Plant_leaf_diseases_dataset_without_augmentation.zip（原始版，约 868MB）
3. wktomo/Tomato_leaf_disease_dataset — data1.zip（番茄叶病，约 41MB）

用法：
  python scripts/download_extra_datasets.py            # 下载全部
  python scripts/download_extra_datasets.py --list      # 仅列出清单不下载
"""
import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DL_DIR = DATA_DIR / "downloads"

# (下载 URL 相对路径, 保存文件名, 说明)
DATASETS = [
    {
        "ns": "OmniData",
        "name": "PlantVillage",
        "path": "raw/Plant_leaf_diseases_dataset_with_augmentation.zip",
        "out": "plantvillage_augmentation.zip",
        "desc": "PlantVillage 增强版（38类）",
    },
    {
        "ns": "OmniData",
        "name": "PlantVillage",
        "path": "raw/Plant_leaf_diseases_dataset_without_augmentation.zip",
        "out": "plantvillage_without_augmentation.zip",
        "desc": "PlantVillage 原始版（38类）",
    },
    {
        "ns": "wktomo",
        "name": "Tomato_leaf_disease_dataset",
        "path": "data1.zip",
        "out": "tomato_leaf_disease.zip",
        "desc": "番茄叶病数据集",
    },
]


def resolve_url(item: dict) -> str:
    return (
        f"https://modelscope.cn/datasets/{item['ns']}/{item['name']}"
        f"/resolve/master/{item['path']}"
    )


def download_one(item: dict) -> Path:
    """下载单个文件，支持断点续传。返回保存路径。"""
    DL_DIR.mkdir(parents=True, exist_ok=True)
    dest = DL_DIR / item["out"]
    url = resolve_url(item)

    # 先探测文件总大小
    total = 0
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=(30, 60))
        total = int(r.headers.get("Content-Length", 0))
        r.close()
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] 探测大小失败：{e}", flush=True)

    done = dest.stat().st_size if dest.exists() else 0
    if total and done >= total:
        print(f"  [skip] {item['desc']} 已存在且完整（{total/1048576:.0f}MB）", flush=True)
        return dest

    headers = {"User-Agent": "Mozilla/5.0"}
    mode = "wb"
    if 0 < done < total:
        headers["Range"] = f"bytes={done}-"
        mode = "ab"

    attempts = 0
    while True:
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as r:
                if r.status_code not in (200, 206):
                    raise RuntimeError(f"HTTP {r.status_code}")
                if mode == "ab" and r.status_code == 200:
                    done = 0
                    mode = "wb"
                last_t = time.time()
                last_done = done
                with open(dest, mode) as f:
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        t = time.time()
                        if t - last_t >= 2.0:
                            dt = t - last_t
                            db = done - last_done
                            speed = (db / dt) / (1024 * 1024) if dt > 0 else 0
                            if total:
                                pct = done / total * 100
                                print(f"  {item['desc']}: {done/1048576:.0f}/{total/1048576:.0f}MB {pct:.1f}% {speed:.1f}MB/s", flush=True)
                            last_t = t
                            last_done = done
            print(f"  [done] {item['desc']} -> {dest.name}（{done/1048576:.1f}MB）", flush=True)
            return dest
        except Exception as e:  # noqa: BLE001
            attempts += 1
            print(f"  [retry {attempts}] {item['desc']}：{e}", flush=True)
            time.sleep(5)
            if attempts > 20:
                raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="仅列出下载清单")
    parser.add_argument("--only", type=int, default=None, help="只下载第 N 项（从 0 开始）")
    args = parser.parse_args()

    print("=" * 60)
    print("病叶数据集下载清单（来源：魔搭 ModelScope 国内 CDN）")
    print("=" * 60)
    for i, item in enumerate(DATASETS):
        print(f"[{i}] {item['desc']}")
        print(f"    URL: {resolve_url(item)}")
    print("=" * 60)

    if args.list:
        return

    items = DATASETS if args.only is None else [DATASETS[args.only]]
    for item in items:
        print(f"\n>>> 开始下载：{item['desc']}", flush=True)
        try:
            download_one(item)
        except Exception as e:  # noqa: BLE001
            print(f"  [fail] {item['desc']}：{e}", flush=True)
            if args.only is None:
                continue
            sys.exit(1)

    print("\n全部下载任务结束。文件位于：", DL_DIR)


if __name__ == "__main__":
    main()
