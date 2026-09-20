"""后端三处修复的独立验证（自足、无残留进程、自写日志）。

(1) 删除 uploads/ 后服务仍可 import 启动（blocking-1）
(2) scripts/verify_pipeline.py 对真实 uvicorn 服务恢复 5/5（blocking-3）
(3) scripts/smoke_test.py 可正常跑通，不再 AttributeError（blocking-4）
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # CNDS
BACKEND = ROOT / "backend"
WORK = ROOT / ".workbuddy" / "verify_work"
PY = sys.executable
ENV = dict(os.environ, YOLO_OFFLINE="true", ULTRALYTICS_OFFLINE="true")

report = {}


def stage(msg):
    with open(WORK / "stage.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def test_startup_without_uploads():
    up = ROOT / "uploads"
    bak = ROOT / "uploads__verify_bak"
    existed = up.exists()
    if existed:
        shutil.move(str(up), str(bak))
    r = None
    try:
        r = subprocess.run(
            [PY, "-c", "import app.main; print('IMPORT_OK')"],
            cwd=str(BACKEND), env=ENV, capture_output=True, text=True, timeout=240,
        )
        ok = "IMPORT_OK" in (r.stdout or "")
        tail = ((r.stdout or "") + (r.stderr or ""))[-900:]
    finally:
        if existed:
            if up.exists():
                try:
                    for child in list(up.iterdir()):
                        shutil.move(str(child), str(bak / child.name))
                    up.rmdir()
                except OSError:
                    pass
            if up.exists():
                shutil.rmtree(str(up), ignore_errors=True)
            shutil.move(str(bak), str(up))
    report["startup_without_uploads"] = {
        "ok": ok, "returncode": r.returncode if r else None, "tail": tail,
    }


def test_verify_pipeline():
    sys.path.insert(0, str(BACKEND))
    os.chdir(str(BACKEND))
    import uvicorn
    from app.main import app

    port = 8011
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(cfg)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    import requests
    ready = False
    for _ in range(240):
        try:
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    out, rc = "", -1
    if ready:
        env = dict(ENV, AGRI_BASE_URL=f"http://127.0.0.1:{port}")
        r = subprocess.run(
            [PY, str(ROOT / "scripts" / "verify_pipeline.py")],
            env=env, capture_output=True, text=True, timeout=300,
        )
        rc = r.returncode
        out = (r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or "")
    (WORK / "verify_pipeline_out.txt").write_text(out, encoding="utf-8")

    server.should_exit = True
    th.join(timeout=20)
    report["verify_pipeline"] = {"ready": ready, "returncode": rc, "tail": out[-800:]}


def test_smoke_test():
    val = ROOT / "data" / "plantvillage" / "val" / "Tomato___Early_blight"
    val.mkdir(parents=True, exist_ok=True)
    (val / "sample.jpg").write_bytes(
        (ROOT / "frontend" / "_demo_leaf_compliant.jpg").read_bytes()
    )
    try:
        r = subprocess.run(
            [PY, str(ROOT / "scripts" / "smoke_test.py")],
            cwd=str(ROOT), env=ENV, capture_output=True, text=True, timeout=300,
        )
        out = (r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or "")
        (WORK / "smoke_out.txt").write_text(out, encoding="utf-8")
        report["smoke_test"] = {
            "returncode": r.returncode,
            "crashed": "AttributeError" in (r.stderr or ""),
            "tail": out[-900:],
        }
    finally:
        for d in (val, val.parent, val.parent.parent, val.parent.parent.parent):
            try:
                d.rmdir()
            except OSError:
                break


def main():
    stage("start")
    test_startup_without_uploads()
    stage("test1 done ok=" + str(report["startup_without_uploads"]["ok"]))
    test_verify_pipeline()
    stage("test2 done rc=" + str(report["verify_pipeline"]["returncode"])
          + " ready=" + str(report["verify_pipeline"]["ready"]))
    test_smoke_test()
    stage("test3 done rc=" + str(report["smoke_test"]["returncode"]))
    (WORK / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stage("ALL_DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        (WORK / "err.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
