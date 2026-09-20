import json
import os
import urllib.error
import urllib.request
from pathlib import Path

env = Path(__file__).parent.parent / ".env"
for line in env.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

key = os.getenv("LLM_API_KEY")
base = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
model = os.getenv("LLM_MODEL", "qwen-plus")

payload = json.dumps(
    {"model": model, "messages": [{"role": "user", "content": "请回复四个字：连接成功"}], "max_tokens": 20}
).encode("utf-8")

req = urllib.request.Request(
    base + "/chat/completions",
    data=payload,
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("STATUS:", r.status)
        print(r.read().decode("utf-8")[:800])
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print(e.read().decode("utf-8")[:800])
except Exception as e:
    print("ERROR:", repr(e))