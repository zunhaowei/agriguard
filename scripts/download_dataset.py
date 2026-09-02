"""下载 PlantVillage data.zip，实时把字节进度写入项目根的 download.js。

面板（进度面板.html）每 3 秒自动刷新并读取 download.js，即可看到
已下载/总量/速度/剩余时间；网络中断会自动从断点续传。
"""
import os
import sys
import time
import json
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ZIP_PATH = DATA_DIR / "data.zip"
PROGRESS_JS = ROOT / "download.js"

URL = "https://hf-mirror.com/datasets/mohanty/PlantVillage/resolve/main/data.zip"
TOTAL = 2184723441  # bytes
CHUNK = 256 * 1024


def now() -> str:
    return time.strftime("%H:%M:%S")


def write_download(**kw) -> None:
    base = {
        "active": True,
        "phase": "downloading",
        "label": "PlantVillage 数据集 data.zip",
        "bytes_done": 0,
        "bytes_total": TOTAL,
        "percent": 0,
        "speed_mbps": 0,
        "eta": "--",
        "updated": now(),
    }
    base.update(kw)
    text = "window.DOWNLOAD = " + json.dumps(base, ensure_ascii=False) + ";\n"
    tmp = PROGRESS_JS.with_suffix(".js.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, PROGRESS_JS)


def download() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    done = ZIP_PATH.stat().st_size if ZIP_PATH.exists() else 0
    write_download(active=True, phase="downloading", bytes_done=done, percent=round(done / TOTAL * 100, 1))

    attempts = 0
    while True:
        headers = {"User-Agent": "Mozilla/5.0"}
        want_resume = 0 < done < TOTAL
        if want_resume:
            headers["Range"] = f"bytes={done}-"
        try:
            r = requests.get(URL, headers=headers, stream=True, timeout=(30, 30))
            if r.status_code not in (200, 206):
                raise RuntimeError(f"HTTP {r.status_code}")
            # 请求了断点但服务器返回 200 → 从头重下
            if want_resume and r.status_code == 200:
                done = 0
            mode = "ab" if done else "wb"
            last_t = time.time()
            last_done = done
            with open(ZIP_PATH, mode) as f:
                for chunk in r.iter_content(chunk_size=CHUNK):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    t = time.time()
                    if t - last_t >= 1.0:
                        dt = t - last_t
                        db = done - last_done
                        speed = (db / dt) / (1024 * 1024) if dt > 0 else 0
                        pct = done / TOTAL * 100
                        eta_s = (TOTAL - done) / (db / dt) if db > 0 else 0
                        mm, ss = divmod(int(eta_s), 60)
                        write_download(
                            phase="downloading",
                            bytes_done=done,
                            percent=round(pct, 1),
                            speed_mbps=round(speed, 1),
                            eta=f"{mm:02d}:{ss:02d}",
                        )
                        print(f"[download] {done/1048576:.0f}/{TOTAL/1048576:.0f} MB  {pct:.1f}%  {speed:.1f} MB/s  eta {mm:02d}:{ss:02d}", flush=True)
                        last_t = t
                        last_done = done
            return  # 下载完成
        except Exception as e:  # noqa: BLE001
            attempts += 1
            msg = f"网络中断/出错，第 {attempts} 次重试（断点续传）：{e}"
            print(f"[download] {msg}", flush=True)
            write_download(phase="retry", label=msg, bytes_done=done, percent=round(done / TOTAL * 100, 1))
            time.sleep(15)
            if attempts > 60:
                raise


def extract() -> None:
    write_download(phase="extracting", label="解压 data.zip 中…", percent=100, speed_mbps=0, eta="00:00")
    EXTRACT = DATA_DIR / "pv_raw"
    EXTRACT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as z:
        names = z.namelist()
        print(f"[extract] 共 {len(names)} 个条目，开始解压…", flush=True)
        for i, member in enumerate(names):
            z.extract(member, EXTRACT)
            if i % 1000 == 0:
                print(f"[extract] {i}/{len(names)}", flush=True)
    write_download(phase="done", label="下载并解压完成", percent=100, bytes_done=TOTAL, bytes_total=TOTAL, speed_mbps=0, eta="00:00")
    print("[extract] 完成，数据位于 data/pv_raw", flush=True)


def main() -> None:
    print(f"[download] 目标：{URL}", flush=True)
    download()
    print("[download] 下载完成", flush=True)
    extract()
    write_download(active=False, phase="done", label="完成", percent=100, bytes_done=TOTAL, bytes_total=TOTAL, speed_mbps=0, eta="00:00")


if __name__ == "__main__":
    main()