"""读写 status.json（进度面板的数据源）。

train.py 等长任务通过这里实时写入，进度面板通过 HTTP 轮询读取。
"""
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "status.json"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def read() -> dict:
    if STATUS.exists():
        try:
            return json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"updated": _now(), "overall": "", "steps": [], "log": [], "download": None, "train": None}


def write(data: dict) -> None:
    data["updated"] = _now()
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATUS)


def update(**fields) -> dict:
    d = read()
    d.update(fields)
    write(d)
    return d


def update_train(**fields) -> None:
    d = read()
    tr = d.get("train") or {"active": True, "label": "训练中", "epoch": 0, "epochs": 30, "top1": None, "loss": None}
    tr.update(fields)
    d["train"] = tr
    write(d)