"""多线程下载 CUDA 版 torch/torchvision wheel（阿里云镜像对单连接限速，多线程可提速）。

用法：
  python scripts/download_torch_cuda.py
下载到 data/downloads/torch_wheels/，完成后用 pip install 本地安装。
"""
import os
import shutil
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "downloads" / "torch_wheels"

FILES = [
    (
        "https://mirrors.aliyun.com/pytorch-wheels/cu126/torch-2.13.0%2Bcu126-cp313-cp313-win_amd64.whl",
        "torch-2.13.0+cu126-cp313-cp313-win_amd64.whl",
    ),
    (
        "https://mirrors.aliyun.com/pytorch-wheels/cu126/torchvision-0.28.0%2Bcu126-cp313-cp313-win_amd64.whl",
        "torchvision-0.28.0+cu126-cp313-cp313-win_amd64.whl",
    ),
]

CHUNK = 4 * 1024 * 1024  # 每块 4MB
THREADS = 16


def get_size(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
    r = urllib.request.urlopen(req, timeout=30)
    size = int(r.headers.get("Content-Length", 0))
    # 某些服务器 HEAD 不支持，退回 GET Range 探测
    if not size:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
        r = urllib.request.urlopen(req, timeout=30)
        cr = r.headers.get("Content-Range", "")
        if "/" in cr:
            size = int(cr.split("/")[-1])
    return size


def download_range(url: str, start: int, end: int, tmp_path: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": f"bytes={start}-{end}"})
    r = urllib.request.urlopen(req, timeout=60)
    data = r.read()
    with open(tmp_path, "wb") as f:
        f.write(data)


def download_file(url: str, name: str):
    dest = OUT / name
    OUT.mkdir(parents=True, exist_ok=True)
    size = get_size(url)
    print(f"{name}: 大小 {size/1048576:.1f} MB", flush=True)

    if dest.exists() and dest.stat().st_size == size:
        print(f"  [skip] 已完整", flush=True)
        return

    # 分块下载到临时目录
    tmp_dir = OUT / f".{name}.parts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    n_parts = (size + CHUNK - 1) // CHUNK
    t0 = time.time()
    done = [0]

    def work(i):
        start = i * CHUNK
        end = min(start + CHUNK, size) - 1
        part_path = tmp_dir / f"{i:05d}.part"
        if part_path.exists() and part_path.stat().st_size == end - start + 1:
            done[0] += end - start + 1
            return
        download_range(url, start, end, part_path)
        done[0] += end - start + 1

    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        list(ex.map(work, range(n_parts)))

    # 合并
    with open(dest, "wb") as out:
        for i in range(n_parts):
            part_path = tmp_dir / f"{i:05d}.part"
            with open(part_path, "rb") as pf:
                shutil.copyfileobj(pf, out, 1024 * 1024)
            part_path.unlink()
    tmp_dir.rmdir()
    dt = time.time() - t0
    print(f"  [done] {name}（{size/1048576:.1f}MB，用时 {dt:.0f}s，平均 {size/1048576/dt:.2f} MB/s）", flush=True)


def main():
    print("=" * 60)
    print("多线程下载 CUDA 版 torch / torchvision")
    print("=" * 60)
    for url, name in FILES:
        print(f">>> {name}", flush=True)
        try:
            download_file(url, name)
        except Exception as e:  # noqa: BLE001
            print(f"  [fail] {name}: {e}", flush=True)
            sys.exit(1)

    print("\n全部下载完成。安装命令：")
    print(f"  .venv/Scripts/python.exe -m pip install --no-index --find-links {OUT} torch torchvision")
    print(f"（或直接 pip install 目录下的两个 whl 文件）")


if __name__ == "__main__":
    main()
