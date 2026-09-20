"""递归下载魔搭（ModelScope）目录结构的数据集（分类文件夹格式）。

用于下载如 ZhouHaoHBU/Tomato_Leaf_Disease 这类「train/<类别>/<图片>.jpg」结构的数据集。
通过 repo/tree 的 Recursive=true 参数递归获取文件列表（分页），逐个下载 blob 文件，
保持目录结构，支持断点续传。

用法：
  python scripts/download_tree_dataset.py --ns ZhouHaoHBU --name Tomato_Leaf_Disease --root train --out data/tomato_leaf_disease
"""
import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://modelscope.cn/api/v1/datasets"


def list_files(ns: str, name: str, root: str, page_size: int = 100):
    """递归列出所有文件（blob），返回 [(path, size), ...] 列表。"""
    files = []
    page = 1
    while True:
        url = (
            f"{API}/{ns}/{name}/repo/tree?Revision=master"
            f"&Root={root}&Recursive=true&PageNumber={page}&PageSize={page_size}"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        data = r.json().get("Data", {})
        batch = data.get("Files", []) or []
        for f in batch:
            if f.get("Type") == "blob":
                files.append((f.get("Path"), f.get("Size", 0)))
        total = data.get("TotalCount", 0)
        if page * page_size >= total or not batch:
            break
        page += 1
    return files


def download_file(ns: str, name: str, rel_path: str, dest: Path) -> bool:
    """下载单个文件到 dest，支持断点续传。"""
    url = f"https://modelscope.cn/datasets/{ns}/{name}/resolve/master/{rel_path}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    done = dest.stat().st_size if dest.exists() else 0

    # 探测总大小
    total = 0
    try:
        with requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=(30, 60)) as r:
            total = int(r.headers.get("Content-Length", 0))
    except Exception:
        pass

    if total and done >= total:
        return True  # 已完整

    headers = {"User-Agent": "Mozilla/5.0"}
    mode = "wb"
    if 0 < done < total:
        headers["Range"] = f"bytes={done}-"
        mode = "ab"
    try:
        with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as r:
            if r.status_code not in (200, 206):
                return False
            with open(dest, mode) as f:
                for chunk in r.iter_content(chunk_size=128 * 1024):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--root", default="train")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_root = Path(args.out)
    if not out_root.is_absolute():
        out_root = ROOT / out_root

    print(f"列出文件：{args.ns}/{args.name} Root={args.root} ...", flush=True)
    files = list_files(args.ns, args.name, args.root)
    print(f"共 {len(files)} 个文件，总大小 {sum(s for _, s in files)/1048576:.1f}MB", flush=True)

    ok = 0
    fail = 0
    for i, (rel_path, size) in enumerate(files):
        # rel_path 形如 train/bacterial_spot/img.jpg，去掉 root 前缀
        rel = rel_path[len(args.root):].lstrip("/")
        dest = out_root / rel
        if download_file(args.ns, args.name, rel_path, dest):
            ok += 1
        else:
            fail += 1
            print(f"  [fail] {rel_path}", flush=True)
        if (i + 1) % 200 == 0:
            print(f"  进度 {i+1}/{len(files)}（成功 {ok} 失败 {fail}）", flush=True)
    print(f"\n完成：成功 {ok} 个，失败 {fail} 个。输出目录：{out_root}", flush=True)
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
