"""用 Chrome DevTools Protocol 抓取产品真实界面截图，供演示视频与海报使用。

【为什么需要这个脚本】
海报（`build_poster.py`）、PPT（`build_pptx.py`）、开发日志（`build_devlog.py`）
都依赖 `media/screens/` 下的真实界面截图，但这些脚本只消费、不生产。
`media/` 曾整体丢失过一次，导致物料无法重建。本脚本把「截图的获取方式」也固化成可复现步骤。

它通过 CDP 驱动无头 Chrome：打开页面 → 点击「使用示例病叶图」→ 等待真实诊断完成
→ 分别截取首页、诊断结论、防治处方三张图。全程使用真实后端与真实模型。

依赖：仅用 venv 已装的 `websockets`（随 uvicorn[standard] 提供），不新增依赖。

用法（需先启动服务）：
    run.bat                                     # 另开一个窗口启动服务
    .venv\\Scripts\\python.exe scripts\\capture_screens.py
"""

import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENS = ROOT / "media" / "screens"
APP = "http://127.0.0.1:8000/"
CDP_PORT = 9222
VIEWPORT = (1440, 1000)

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome() -> str:
    for p in CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit("未找到 Chrome/Edge 可执行文件")


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_http(url: str, timeout: float = 60) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.6)
    return False


class CDP:
    """极简 CDP 客户端：只实现本脚本用到的几个命令。"""

    def __init__(self, ws_url: str):
        import asyncio

        import websockets

        self._asyncio = asyncio
        self._ws = websockets
        self._url = ws_url
        self._id = 0
        self._ws_obj = None
        self._loop = asyncio.new_event_loop()

    def __enter__(self):
        self._ws_obj = self._loop.run_until_complete(self._ws.connect(self._url, max_size=64 * 1024 * 1024))
        return self

    def __exit__(self, *exc):
        try:
            self._loop.run_until_complete(self._ws_obj.close())
        finally:
            self._loop.close()

    def call(self, method: str, **params):
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params}
        self._loop.run_until_complete(self._ws_obj.send(json.dumps(msg)))
        while True:
            raw = self._loop.run_until_complete(self._ws_obj.recv())
            data = json.loads(raw)
            if data.get("id") == mid:
                if "error" in data:
                    raise RuntimeError(f"{method} -> {data['error']}")
                return data.get("result", {})

    def eval_js(self, expr: str, await_promise: bool = False):
        r = self.call(
            "Runtime.evaluate",
            expression=expr,
            returnByValue=True,
            awaitPromise=await_promise,
        )
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS 异常: {r['exceptionDetails'].get('text')}")
        return r.get("result", {}).get("value")


def rect_js(selector: str) -> str:
    return (
        "(() => { const e = document.querySelector(%s); if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return JSON.stringify({x:r.x+window.scrollX,y:r.y+window.scrollY,w:r.width,h:r.height}); })()"
        % json.dumps(selector)
    )


def shot(cdp: CDP, selector, out: Path, pad: int = 16):
    """按元素截取，四周留 pad 的呼吸位。"""
    raw = cdp.eval_js(rect_js(selector))
    if not raw:
        print(f"  [跳过] 找不到元素 {selector}")
        return False
    r = json.loads(raw)
    clip = {
        "x": max(0, r["x"] - pad),
        "y": max(0, r["y"] - pad),
        "width": r["w"] + pad * 2,
        "height": r["h"] + pad * 2,
        "scale": 2,  # 2 倍像素密度，放大后文字仍清晰
    }
    res = cdp.call("Page.captureScreenshot", format="png", clip=clip, captureBeyondViewport=True)
    out.write_bytes(base64.b64decode(res["data"]))
    print(f"  已保存 {out.name}  {clip['width']:.0f}x{clip['height']:.0f} @2x  "
          f"{out.stat().st_size/1024:.0f} KB")
    return True


def main() -> int:
    SCREENS.mkdir(parents=True, exist_ok=True)

    if not port_open(8000):
        print("[错误] 服务未在 127.0.0.1:8000 运行。请先启动 run.bat 或 uvicorn，再运行本脚本。")
        return 1
    if not wait_http(APP + "health", 20):
        print("[错误] 服务无响应 /health")
        return 1

    chrome = find_chrome()
    profile = tempfile.mkdtemp(prefix="agri_shot_")
    proc = subprocess.Popen(
        [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--force-device-scale-factor=2",
            f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    try:
        # 等调试端口就绪
        ws_url = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=2) as r:
                    targets = json.load(r)
                pages = [t for t in targets if t.get("type") == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws_url:
            print("[错误] 无法连接 Chrome 调试端口")
            return 1

        with CDP(ws_url) as cdp:
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride",
                     width=VIEWPORT[0], height=VIEWPORT[1], deviceScaleFactor=2, mobile=False)

            print("打开首页…")
            cdp.call("Page.navigate", url=APP)
            for _ in range(60):
                if cdp.eval_js("document.readyState") == "complete":
                    break
                time.sleep(0.4)
            time.sleep(2.5)  # 等 /api/v1/meta 渲染完作物清单

            print("[1/3] 首页")
            shot(cdp, "main", SCREENS / "01_home.png")

            print("点击「使用示例病叶图」并等待真实诊断…")
            cdp.eval_js("document.getElementById('demo-btn').click()")
            ok = False
            for i in range(120):  # 最多等 120s（含大模型处方）
                st = cdp.eval_js(
                    "(() => { const e=document.getElementById('result');"
                    " return e && !e.hidden ? 'ready' : 'wait'; })()"
                )
                if st == "ready":
                    ok = True
                    break
                time.sleep(1)
            if not ok:
                print("[警告] 等待诊断结果超时，仍尝试截图")

            time.sleep(1.5)
            print("[2/3] 诊断结论")
            shot(cdp, "#result", SCREENS / "02_result.png")

            print("[3/3] 防治处方")
            rx_card = cdp.eval_js(
                "(() => { const p=document.getElementById('prescription');"
                " if(!p) return null; const c=p.closest('section'); return c ? 'ok' : null; })()"
            )
            shot(cdp, "#prescription" if rx_card else "#result", SCREENS / "04_bottom_prescription.png")

            # 额外：热力图单图（海报/PPT 常单独用）
            shot(cdp, "#heatmap-img", SCREENS / "03_heatmap.png")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)

    print("\n完成。产物：")
    for f in sorted(SCREENS.glob("*.png")):
        print(f"  {f.name:32s} {f.stat().st_size/1024:8.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
