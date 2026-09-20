"""路径与运行配置。

【本次审查的两处修正】

1. **消除 import 期副作用**。
   原实现在 import 时就会 `mkdir` 三个目录（含体积很大的 data/），
   导致任何 `import app.config` 都在磁盘上产生副作用，测试与工具链无法干净隔离。
   现改为显式 `ensure_dirs()`，由应用启动钩子调用。

2. **修正兜底模型类型错误（P0 正确性缺陷）**。
   原 `FALLBACK_MODEL = "yolo11n.pt"` 指向的是**检测**模型，而 `detector.load()`
   会无条件访问分类头独有的 `.conv` 属性（注册 forward hook 用）。二者不匹配，
   实测直接抛 `AttributeError: 'Detect' object has no attribute 'conv'`——
   也就是说 `models/best.pt` 一旦缺失，程序不是"降级"，而是**启动即崩**。
   现改为同目录下已存在的**分类**权重 `models/yolo11n-cls.pt`，并加存在性断言。

3. 原实现手写 .env 解析（不处理引号 / `export` 前缀 / 行尾注释 / BOM），
   而 python-dotenv 早已安装却未被使用。现统一改用 `load_dotenv`。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"

# 生产权重
MODEL_PATH = MODELS_DIR / "best.pt"
# 兜底权重：必须是【分类】模型。yolo11n.pt 是检测模型，不可用作分类兜底。
FALLBACK_MODEL_PATH = MODELS_DIR / "yolo11n-cls.pt"

# ---------------------------------------------------------------------------
# .env 加载
# ---------------------------------------------------------------------------
# override=False：已存在的真实环境变量优先于 .env 文件，符合 12-factor 惯例。
# 这样 CI / 演示机可以用环境变量临时覆盖，而不用改文件。
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=False)

# 占位符防护：
# `.env.example` 里写的是 sk-your-key-here。若有人误把示例文件复制成 .env，
# 程序会以为"已配置密钥"而真的发起 HTTP 请求，每次都要等 30 秒超时——
# 在现场演示时这是致命事故。因此显式识别占位符并视为未配置。
_PLACEHOLDER_MARKERS = ("your-key", "your_key", "sk-xxx", "changeme", "替换", "填入")


def _read_llm_key() -> str:
    key = (os.getenv("LLM_API_KEY") or "").strip()
    if not key:
        return ""
    lowered = key.lower()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        return ""
    # 通义千问的密钥形如 sk- 开头且有一定长度；过短的显然是无效值
    if len(key) < 16:
        return ""
    return key


LLM_API_KEY = _read_llm_key()
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).strip()
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus").strip()
# 单次 LLM 调用的超时。原实现只有 timeout=30 且不区分连接/读取超时，
# 断网时会把请求线程拖满 30 秒。现拆分为 (连接, 读取) 两段并整体收紧。
LLM_CONNECT_TIMEOUT = float(os.getenv("LLM_CONNECT_TIMEOUT", "3.5"))
LLM_READ_TIMEOUT = float(os.getenv("LLM_READ_TIMEOUT", "12"))

# 是否启用大模型处方。False 时直接走内置模板，不再发起网络请求。
LLM_ENABLED = bool(LLM_API_KEY)

# 离线优先：ultralytics 在找不到权重/做 AMP 检查时会尝试联网下载，
# 而比赛现场网络不可控。默认置为离线模式，模型一律从本地加载。
os.environ.setdefault("YOLO_OFFLINE", "true")
os.environ.setdefault("ULTRALYTICS_OFFLINE", "true")
# 关闭 ultralytics 的匿名遥测，避免演示机上出现无关外连
os.environ.setdefault("YOLO_VERBOSE", "false")


def ensure_dirs() -> None:
    """显式创建运行期所需目录。由应用启动钩子调用，不再在 import 时执行。"""
    for d in (MODELS_DIR, UPLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)


def resolve_model_path() -> Path:
    """按优先级返回可用的模型权重路径。

    返回 MODEL_PATH 表示用生产权重；返回 FALLBACK_MODEL_PATH 表示降级。
    两者都不存在时抛 FileNotFoundError，让问题在启动期暴露，
    而不是等到第一个请求进来才崩。
    """
    if MODEL_PATH.exists():
        return MODEL_PATH
    if FALLBACK_MODEL_PATH.exists():
        return FALLBACK_MODEL_PATH
    raise FileNotFoundError(
        "未找到任何可用的分类模型权重。请确认以下至少一个文件存在：\n"
        f"  - {MODEL_PATH}（生产权重）\n"
        f"  - {FALLBACK_MODEL_PATH}（兜底权重）"
    )
