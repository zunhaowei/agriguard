"""等待训练跑满目标 epoch，随后把最终 best.pt 复制到 models/。

用法：.venv\\Scripts\\python.exe -B scripts\\finalize_train.py [--epochs 30]
"""
import argparse
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "runs" / "agriguard" / "results.csv"
BEST_SRC = ROOT / "runs" / "agriguard" / "weights" / "best.pt"
BEST_DST = ROOT / "models" / "best.pt"


def current_epoch() -> int:
    try:
        lines = RESULTS.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) < 2:
            return 0
        return int(lines[-1].split(",")[0])
    except Exception:
        return 0


def main(target: int) -> None:
    print(f"[finalize] 等待训练完成 (target={target} epochs)...", flush=True)
    last = -1
    while True:
        e = current_epoch()
        if e != last:
            print(f"[finalize] 当前 epoch: {e}/{target}  {time.strftime('%H:%M:%S')}", flush=True)
            last = e
        if e >= target:
            break
        time.sleep(30)

    time.sleep(10)
    if BEST_SRC.exists():
        shutil.copy2(BEST_SRC, BEST_DST)
        print(f"[finalize] 已复制 best.pt -> models/best.pt ({BEST_DST.stat().st_size} bytes)", flush=True)
    else:
        print("[finalize] 警告：未找到 runs/agriguard/weights/best.pt", flush=True)
    print("[finalize] DONE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()
    main(args.epochs)