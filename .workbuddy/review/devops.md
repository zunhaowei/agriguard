# 运维审计报告 — 禾目 AgriGuard

- 审计人：卜宕机（运维工程师）
- 日期：2026-09-20
- 范围：依赖可复现性、配置健壮性、部署与现场演示健壮性（本机离线演示形态）
- 项目根：`D:\shuangti11\ICAN\ican\CNDS`
- 约束遵守：本审计**未修改任何项目代码或脚本**；所有临时探测脚本与输出集中放 `.workbuddy\review\`

> 说明：审计期间团队其他成员正在并行落盘修复（`requirements.txt` / `setup.bat` / `run.bat` / `.env.example` / `.gitignore` / `backend/app/*` 均已被重写，且已 `git init` 并提交 3 次）。因此本报告**同时给出**「问题定性」与「对已落盘修复的独立复核」，对已修的项标注复核结论，对未闭合的项给出待办。

---

## 0. 环境实测（以实测为准，纠正既有文档与任务书口径）

实测命令与工具：`.venv\Scripts\python.exe`（PowerShell 重定向落盘后读取，bash 不可用）。

| 项 | 实测值 | 与既有口径的差异 |
|---|---|---|
| Python | **3.13.14**（`main, Jun 11 2026`, MSC v.1944 64bit） | 交接文档写 3.12；任务书写 3.13.12。`pyvenv.cfg` 里 `version=3.13.14`，但 `home` 指向名为 `3.13.12` 的目录 |
| OS | Windows 11 10.0.26200 | — |
| torch | **2.13.0+cu126** | 交接文档写 2.5.1+cu121 |
| torchvision | **0.28.0+cu126** | 同上 |
| torch.version.cuda / cuDNN | 12.6 / 91002 | — |
| ultralytics | **8.4.137** | 与任务书一致 |
| numpy / opencv | **2.5.3** / **5.0.0.93** | 与任务书一致 |
| fastapi / starlette / pydantic / uvicorn | 0.141.1 / 1.6.0 / 2.13.5 / 0.53.0 | — |
| requests / pillow / python-dotenv / python-multipart | 2.34.2 / 12.3.0 / 1.2.3 / 0.0.32 | — |
| matplotlib / polars / psutil | 3.11.2 / 1.44.2 / 7.2.2 | 见 A2：**polars、psutil 无任何代码引用** |
| GPU | **NVIDIA GeForce RTX 4050 Laptop GPU** | ⚠️ 任务书写「RTX 4060 Laptop 8GB」，**不符**。交接文档写 4050 才是对的 |
| 显存 | **6141 MiB（6GB）**，当前占用 1543 MiB | ⚠️ 任务书「8GB」不成立。影响 B3「显存不足」行的预算 |
| 驱动 / CUDA | **590.26 / CUDA 12.9** | ⚠️ 任务书「驱动 592.00 / CUDA 13.1」不符 |

**结论纠偏**：显存预算是 **6GB 而非 8GB**，且桌面已常驻占用约 1.5GB（Edge/微信/VS Code 等 C+G 进程）。演示前建议关闭这些进程，见 B4 清单。

### 磁盘与仓库现状（实测）

| 路径 | 体积 | 文件数 | 状态 |
|---|---|---|---|
| `data/` | 892.8 MB | 60,177 | 只剩 `plantvillage/`；`downloads/`、`plantvillage_combined/`、`plantvillage_balanced/`、`datasets_raw/` **已不存在**（约 7GB 冗余已被清理） |
| `.venv/` | 4574.1 MB | 25,986 | 未入库 |
| `runs/agriguard_v2/` | 9.1 MB | 17 | **参赛证据已入库** |
| `uploads/` | 0.2 MB | 14 | 已从 259 个残骸清到 14 个 |
| `models/` | 8.7 MB | 2 | `best.pt` + `yolo11n-cls.pt`（`best_old.pt` 已移入备份） |
| `scripts/` | 0.2 MB | 35 | 其中 12 个素材脚本仍为孤儿 |
| `.workbuddy/` | 3.5 MB | 31 | 含 `backup/2026-09-20/` 8 个文件 |
| `.git/` | 9.45 MB | — | 3 次提交、81 个跟踪文件 |

`git log --oneline`（3 条）：`77344cf` docs 后端修复记录 / `bf94dae` docs 项目审查报告 / `d5b8053` chore 首个版本控制快照。

---

## A. 依赖与配置项检查

### A1. 可复现性审计：干净机器从零跑起来的正确步骤

**当前可跑步骤（本机实测已验证）**

```powershell
# 0. 前置：确认 Python 3.13 存在（实测 .venv 基础解释器为 3.13.14）
py -0p                      # 期望列出 3.13；本机实测输出 3.14/3.12/3.11，未见 3.13 注册项
                            # 说明：本机 3.13 由 workbuddy 托管于
                            #   C:\Users\weizunhao\.workbuddy\binaries\python\versions\3.13.12\python.exe（实测 --version = 3.13.14）

# 1. 直接用现有 .venv（本机已就绪，勿重装）
cd D:\shuangti11\ICAN\ican\CNDS
.venv\Scripts\python.exe -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# 实测期望：2.13.0+cu126 True NVIDIA GeForce RTX 4050 Laptop GPU

# 2. 确认权重与目录
dir models\best.pt          # 3,281,538 字节

# 3. 启动
run.bat                     # 或：cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 4. 自检
curl.exe http://127.0.0.1:8000/health
```

**从零重建（新机器）时三份文档会各自在哪里翻车**

| # | 位置 | 会怎样失败 | 证据 |
|---|---|---|---|
| F1 | `setup.bat`（新版）CUDA 分支 | `--index-url https://mirrors.aliyun.com/pytorch-wheels/cu126/` 对 pip 而言是 **PEP503 simple 索引**，pip 会请求 `.../cu126/torch/`，实测 **HTTP 404**。于是该分支拿不到 cu126 wheel，只能回落 `--extra-index-url https://mirrors.aliyun.com/pypi/simple/` 上的**无本地版本号** `torch-2.13.0-cp313-cp313-win_amd64.whl`。**无法保证复现实测的 `2.13.0+cu126`** | 见 §C `evidence` E1–E4 |
| F2 | 交接文档 §11 | 写 `py -3.12 -m venv .venv` + `torch==2.5.1+cu121`，与实测 3.13/2.13.0+cu126 全不符；照抄会得到**另一个环境**（且 3.12 下有无 cu126 wheel 未验证） | 交接文档 line 410–413 |
| F3 | 交接文档 §11 第 4 步 | `copy runs\agriguard\weights\best.pt models\best.pt` —— 实际目录是 `runs\agriguard_v2\`，且 `runs/**/weights/` 已通过 `-f` 修复前就已存在两份 | 交接文档 line 419；`runs/` 实测仅 `agriguard_v2` |
| F4 | 交接文档 §11 第 6 步 | `serve_panel.bat` 已删除（移入备份），照抄会「文件不存在」 | 根目录实测无该文件 |
| F5 | `requirements.txt`（原版） | 无 torch/torchvision，单独 `pip install -r` 得到**没有 torch 的坏环境**；新版已加醒目警告并改由 `setup.bat` 负责安装，**已修复** | 新版 requirements.txt line 3–5 |
| F6 | `requirements.txt`（原版） | `ultralytics>=8.2` 会装到 **8.4.153**，与 `detector.py` 的 forward hook 冲突（`cannot pickle '_thread.lock'`），推理直接崩。新版已锁 `==8.4.137`，**已修复** | 新版 line 7–12；`.workbuddy/memory/2026-09-16.md` line 14 |
| F7 | 托管 Python 路径依赖 | `.venv\pyvenv.cfg` 的 `home` 指向 `C:\Users\19057\...\python\versions\3.13.12`（**该路径实测不存在**，当前用户为 `weizunhao`）。.venv 之所以仍可运行，是解释器解析走了另一条路径；换机/换用户后**必须先重建 venv**，不能直接拷贝 | 实测 `pyvenv.cfg`: `home = C:\Users\19057\...`，`Test-Path` = False |

**依赖清单（按"必须锁死 / 可放宽 / CUDA 相关 / 仅训练用 / 已装但未使用"分类，均以实测版本为锚点）**

| 类别 | 包 | 实测版本 | 处置 |
|---|---|---|---|
| 必须锁死 | `ultralytics` | 8.4.137 | `==8.4.137`。理由：8.4.153 的 `deepcopy` 与 forward hook 冲突（有日志实证） |
| 必须锁死 | `torch` / `torchvision` | 2.13.0+cu126 / 0.28.0+cu126 | 由 `setup.bat` 安装；**必须带 `+cu126` 本地版本号 + `-f` find-links** |
| CUDA 相关 | `torch`、`torchvision`（cu126 wheel） | 同上 | 索引：`https://mirrors.aliyun.com/pytorch-wheels/cu126/`，该目录实测含 1298 个 whl，**含 `torch-2.13.0+cu126-cp313-cp313-win_amd64.whl`** |
| 可放宽（但建议注明锚点） | `numpy` | 2.5.3 | `>=1.26,<3.0` 可行；锚定 2.5.3 |
| 可放宽（但建议注明锚点） | `opencv-python` | 5.0.0.93 | `>=4.9,<6.0` 可行；锚定 5.0.0.93 |
| 可放宽 | `fastapi`/`starlette`/`pydantic`/`uvicorn`/`pillow`/`requests`/`python-multipart` | 见 §0 | 保持范围内 |
| 运行时必需 | `python-dotenv` | 1.2.3 | **新版 `config.py` 已实际使用**（原版是死依赖），保留 |
| 仅训练用 | `matplotlib` | 3.11.2 | 仅 `scripts/build_supporting.py`、`scripts/ppt_assets.py` 与 ultralytics 训练绘图使用 → 归 `requirements-train.txt` |
| 仅训练用 | `polars` | 1.44.2 | **全项目 `*.py` 无任何引用**（grep 0 命中）→ 建议**删除**，不进任何 requirements |
| 已装但未使用 | `psutil` | 7.2.2 | **全项目 `*.py` 无任何引用**（原为已废弃进度面板所用）→ 从交付环境移除 |
| 已装但未使用 | `opencv-python-headless` | 未安装 | 无需引入；注意不要与 `opencv-python` 同时装 |

**numpy 2.x / opencv 5.x 大版本跨度风险评估**

- `numpy 2.5.3`：本项目对 numpy 的用法是 `np.array/np.cov/np.linalg.inv/np.einsum/np.histogram/astype` 等稳定 API，未使用 `np.float_`/`np.NaN` 等 2.0 移除项；**实测端到端通过**（识别 + 热力图）。风险等级：低。但 `torch 2.13` 与 `numpy 2.x` 的 ABI 需同批安装，**不可单独升降级 numpy**。
- `opencv-python 5.0.0.93`：5.x 相对 4.x 的已知破坏性变更主要在 `cv2.findContours` 返回值与部分 legacy 常量；本项目 3 处调用（`precheck.leaf_foreground_mask`、`gradcam` 的 `applyColorMap/addWeighted`）已在 5.0.0.93 上实测通过。风险等级：低-中（若降到 4.x 需重跑 `verify_pipeline.py`）。
- **结论**：两处跨度**不构成当前阻塞**，但都属于「大版本 + 无 CI 门禁」的组合。补救见 A2 的锚点注释与 §C 的 Silver 差距表。

### A2. 版本锁定方案（新版 `requirements.txt` / `requirements-train.txt`）

团队已产出两文件，本审计**复核通过并给出两处收口**。建议最终内容如下。

**`requirements.txt`（推理运行时最小集，直接给完整文件内容）**

```text
# 禾目 AgriGuard —— 推理运行时依赖（最小集）
#
# 安装请用 setup.bat，不要直接 pip install -r 本文件：
# PyTorch 需要按本机 CUDA 版本从对应 wheel 索引单独安装，
# 直接跑本文件会装成 CPU 版，导致 GPU 推理失效（setup.bat 已处理这个顺序）。
#
# [必须锁死] ultralytics 锁定 8.4.137，不要放宽：
#    8.4.153 的 predict 会对模型做 deepcopy，与 detector.py 的 forward hook 冲突，
#    抛 "cannot pickle '_thread.lock' object" 导致推理完全不可用。
#    8.4.137 为本项目实测验证版本。
#    修改此版本号前，请先跑 scripts/verify_pipeline.py 确认热力图仍能生成。
ultralytics==8.4.137

# Web 服务
fastapi>=0.115,<1.0
uvicorn[standard]>=0.29,<1.0
python-multipart>=0.0.9
pydantic>=2.6,<3.0

# 配置加载（config.py 使用 python-dotenv 解析 .env）
python-dotenv>=1.0,<2.0

# 数值与图像
# 已实测锚点：numpy 2.5.3 / opencv-python 5.0.0.93 上端到端通过。
# 这两个包都属于大版本跨度，降级/升级后必须重跑 scripts/verify_pipeline.py。
numpy>=1.26,<3.0
opencv-python>=4.9,<6.0
pillow>=10.0

# 大模型处方（通义千问兼容 OpenAI 协议）
requests>=2.31,<3.0

# [CUDA 相关] torch / torchvision 不写在这里，由 setup.bat 按 CUDA 分支安装。
# 必须使用带本地版本号的形式与 find-links 索引（本机实测环境）：
#   torch==2.13.0+cu126  torchvision==0.28.0+cu126
#   -f https://mirrors.aliyun.com/pytorch-wheels/cu126/
#   -i https://mirrors.aliyun.com/pypi/simple/
# 注意：不要用 --index-url 指向 pytorch-wheels 目录（实测 .../cu126/torch/ 为 404）。
```

**`requirements-train.txt`（仅训练/重训用）**

```text
# 禾目 AgriGuard —— 训练与数据处理专用依赖（推理部署不需要）
#
# 安装：
#   .venv\Scripts\python.exe -m pip install -r requirements-train.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

-r requirements.txt

# ultralytics 训练与结果绘图路径使用
matplotlib>=3.8
```

**相对当前落盘版本的两处收口**：
1. **删除 `polars>=1.0`** —— 全项目 0 引用（实测 grep 命中 0），属"装了不用"，留着只增加安装失败面。
2. **`requirements.txt` 补一段 CUDA 安装注释（已含在上述文本）** —— 把「必须 `+cu126` + `-f`」写进事实来源文件，避免下一个人照着 `setup.bat` 的 `--index-url` 继续错。

### A3. `.env` 处理方案

**团队已落盘，复核通过**：`config.py` line 21–74。

- 手写解析 → `python-dotenv`：已替换为 `load_dotenv(_ENV_FILE, override=False)`，正确处理 BOM / `export` 前缀 / 引号 / 行尾注释 / 空值（原版这 4 类写法会**全部静默失效**，`backend.md` 有实测记录）。
- 占位符防护：`_PLACEHOLDER_MARKERS = ("your-key", "your_key", "sk-xxx", "changeme", "替换", "填入")` + 长度 <16 视为未配置 → `LLM_API_KEY=""` → `LLM_ENABLED=False` → 直接走模板，**不发网络请求**。
- 超时收紧：`(connect=3.5s, read=12s)` 双段超时（原版 `timeout=30` 单段，断网最坏拖满 30s，且发生在阻塞事件循环里）。

**复核发现的 1 处不一致（建议收口）**

`.env.example` 里宣传了 `LLM_ENABLED=true`，但 `config.py` **从不读取这个变量**（`LLM_ENABLED = bool(LLM_API_KEY)`，由密钥有效性推导）。后果：用户在 `.env` 里写 `LLM_ENABLED=false` 期望关闭大模型时，只要密钥有效，**大模型仍会被启用** —— 一份"看起来能配、实际不起作用"的开关。建议二选一：
- 让 `config.LLM_ENABLED = env_bool("LLM_ENABLED", True) and bool(LLM_API_KEY)`；或
- 从 `.env.example` 删除该行，只保留"填了有效密钥即启用"的口径。

**建议的 `.env.example`（改进版，完整内容）**

```text
# 禾目 AgriGuard 环境变量模板
#
# 使用方法：
#   1) 把本文件复制为 .env（同目录）
#   2) 把 LLM_API_KEY 换成你自己的真实密钥
#   3) 重启服务
#
# 重要：
#   - .env 已被 .gitignore 忽略，切勿提交到公开仓库。
#   - 若保留了下面的示例占位值（含 "your-key" 字样）或密钥长度不足 16 位，
#     程序会识别为「未配置」，直接走内置模板处方，不发起任何网络请求。
#     这是为了避免误把示例值当真实密钥，导致每次请求都等满超时
#     （现场演示的致命事故）。
#   - 未配置密钥时功能完整，只是处方不个性化；响应体 prescription_source 字段
#     会如实标注 "template"，答辩口径请与之保持一致。

# 通义千问 / 阿里云百炼（DashScope 兼容 OpenAI 协议）
# 获取地址：https://bailian.console.aliyun.com/
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus

# 大模型调用超时（秒）。断网时按这两项上限返回，不会长时间挂起。
# 连接超时保持较小，避免网络不通时拖住请求线程。
LLM_CONNECT_TIMEOUT=3.5
LLM_READ_TIMEOUT=12
```

（相对当前版本：删除 `LLM_ENABLED=true` 这一"无效开关"，或按上面方案让它真正生效。）

### A4. 启动脚本加固

**`run.bat` 复核**：已实现 venv 检查、模型检查、端口占用检查、`--host 127.0.0.1`、异常 `pause`、`cd backend` 后用绝对路径 venv 解释器。**改进点 3 条**（见下）。

**`setup.bat` 复核**：已实现 CUDA/CPU 分支、Python 探测、失败 `pause`、装完自检。**但 CUDA 分支存在 F1 缺陷**（见 A1），必须修。

**建议的新版 `run.bat` 关键片段（仅列改动，完整文件由后端/运维在审查后统一落盘）**

```bat
@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 禾目 AgriGuard - 推理服务 (127.0.0.1:8000)      REM [新增] 窗口标题可辨识

set "VENVPY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENVPY%" (
    echo [错误] 未找到虚拟环境：%VENVPY%
    echo        请先双击运行 setup.bat 完成环境安装。
    pause & exit /b 1
)

if not exist "models\best.pt" (
    echo [错误] 未找到生产权重 models\best.pt。
    echo        服务会回落到 models\yolo11n-cls.pt，识别结果无实际意义，禁止用于演示。
    pause & exit /b 1
)

netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [错误] 端口 8000 已被占用。查看占用：netstat -ano ^| findstr :8000
    pause & exit /b 1
)

set PYTHONDONTWRITEBYTECODE=1
set YOLO_OFFLINE=true
set YOLO_VERBOSE=false                                  REM [修正] 去掉无效的 ULTRALYTICS_OFFLINE

cd backend
echo 启动中…… 首次启动会预加载模型（实测约 5-8 秒），请稍候。
echo 启动完成后浏览器访问：http://127.0.0.1:8000
echo 停止服务：在本窗口按 Ctrl+C
"%VENVPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --timeout-keep-alive 5
if errorlevel 1 ( echo. & echo [错误] 服务异常退出，请查看上方报错信息。 & pause & exit /b 1 )
endlocal
```

改动理由：
1. `title` —— 演示时多窗口并存，标题可辨识是硬要求（原 `run.bat` 无）。
2. 删 `ULTRALYTICS_OFFLINE` —— **实测该环境变量在 ultralytics 8.4.137 中零引用**，设了不生效（见 B2），留着会误导下一个人以为离线已双保险。
3. `models\best.pt` 从"警告后继续"改为"**拒绝启动**" —— 用兜底权重出结果去演示，比服务起不来更危险（会拿无意义结果当结论）。若确需联调，另给一个 `run-debug.bat`。
4. `--workers 1` 显式化 —— 单张 GPU 上多 worker 会各自加载一份模型（显存翻倍），必须锁死 1。
5. `--timeout-keep-alive 5` —— 本机演示无长连接需求，缩短 uvicorn 保持连接时间，便于快速重启。

**建议的新版 `setup.bat` CUDA 分支（修正 F1，仅列改动）**

```bat
if "%CHOICE%"=="2" (
    echo [4/5] 安装 CPU 版 PyTorch ...
    "%PY%" -m pip install "torch>=2.4" "torchvision" ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo [4/5] 安装 CUDA 12.6 版 PyTorch ...
    REM 必须：本地版本号 +1 个 find-links 索引（不要用 --index-url 指向该目录，实测 404）
    "%PY%" -m pip install "torch==2.13.0+cu126" "torchvision==0.28.0+cu126" ^
        -f https://mirrors.aliyun.com/pytorch-wheels/cu126/ ^
        -i https://mirrors.aliyun.com/pypi/simple/
)
if errorlevel 1 ( echo [错误] PyTorch 安装失败。 & pause & exit /b 1 )

REM [新增] 装完必须断言 CUDA 真的可用，否则 CUDA 分支"静默退化成 CPU"
"%PY%" -c "import torch,sys; ok=torch.cuda.is_available(); print('torch',torch.__version__,'cuda_available',ok); sys.exit(0 if ok else 1)"
if errorlevel 1 ( echo [错误] PyTorch 已安装但 CUDA 不可用。请检查驱动版本或改用 CPU 分支。 & pause & exit /b 1 )
```

**`serve_panel.bat` 处置建议：删除（已删除，无需恢复）**

理由（三条，任一条已足够）：
1. 它以 `python -m http.server 8001 --bind 127.0.0.1` 托管**项目根目录**，一旦 `.env` 存在，`http://127.0.0.1:8001/.env` 可直接读取明文 API Key。虽然绑定 127.0.0.1，但在同机多人/远程控制软件场景仍是可利用的密钥外泄面。
2. 其唯一用途是驱动已废弃的进度面板 —— 训练早已结束，`status.json` 的 `steps`/`overall` 为空数组，功能已死。
3. 现状实测：根目录已无 `serve_panel.bat`，已移入 `.workbuddy\backup\2026-09-20\`。**建议在确认无回归后连备份一起清掉**（备份保留期见 B5）。

### A5. `.gitignore` 重设计

团队已重写并落盘，**复核通过**（关键规则实测生效，见 §C E9）。设计目标「代码进版本控制、12.5GB 数据不进、参赛证据必须进」已达成。保留其内容，两处小收口：

1. `!data/.gitkeep` 与 `!uploads/.gitkeep` 是**空规则** —— 实测这两个 `.gitkeep` 文件都不存在，规则不产生任何效果。建议要么真的落两个 `.gitkeep` 进仓库（让目录结构可被克隆复现），要么删掉这两行避免误导。
2. `_*.txt` / `_*.json` 作为"本机临时输出"忽略规则，会**连带忽略**任何以下划线开头的合法交付物（如本项目的 `frontend/_demo_leaf_compliant.jpg` 属于下划线开头但是正式资源）。当前该文件靠自带后缀扩展名绕开，规则暂无实害；但建议把规则收窄为 `_tmp_*` / `_ops_*` / `_qa_*`，避免下次误伤。

**建议最终内容（完整）**

```gitignore
# ============================================================================
# 禾目 AgriGuard .gitignore
#
# 设计原则：「代码进版本控制，大体积数据不进，但参赛证据必须进」
#
# 背景：忽略 runs/ 与 data/ 整体会把参赛原创性硬证据（results.csv、
# 混淆矩阵、训练曲线）一起挡在版本控制之外（iCAN 原创性 20 分要求
# "开发过程可追溯"）。因此改为「忽略 runs 下的批次预览图与权重副本，
# 保留训练记录」。
# ============================================================================

# --- 密钥（严禁提交）---
.env
.env.local
*.local

# --- Python ---
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.ipynb_checkpoints/

# --- 数据集（体量大，可由脚本重新下载整理）---
data/*

# --- 运行时产物（用户上传内容属于用户数据，不进仓库）---
uploads/*

# --- 训练产物 ---
runs/**/weights/
runs/**/train_batch*.jpg
runs/**/val_batch*.jpg
runs/**/*.cache
runs/**/labels.jpg

# --- 媒体素材（体积大；如需交付请单独打包）---
media/
*.mp4
*.mov
素材与源代码/
参赛材料/

# --- 构建 / 临时目录 ---
.chrome_tmp/
.edge_tmp/
.edge_tmp_b/
_lo_profile/
_supporting_stage/
.bak/
*.bak

# --- 本机日志与临时输出（收窄前缀，避免误伤 _demo_*.jpg 一类正式资源）---
*.log
_tmp_*
_ops_*
_qa_*
_verify_*

# --- IDE / 系统 ---
.idea/
.vscode/
.DS_Store
Thumbs.db
desktop.ini

# --- 明确保留 ---
!requirements.txt
!requirements-train.txt
!docs/*.md
```

---

## B. 部署与演示健壮性（对应巡展"现场演示效果 50 分"）

### B1. 冷启动预算（实测）

**测量方法**：进程内计时 `import app.main` / `detector.load()` / 连续 3 次 `detect()`；另起真实 uvicorn 子进程（`127.0.0.1:8011`）轮询 `/health` 计时并 POST `/predict`。

| 环节 | 实测耗时 | 说明 |
|---|---|---|
| `import app.main`（含 import torch） | **3.097 s** | 占总耗时大头 |
| `detector.load()`（`YOLO(best.pt)` + 注册 hook + 预计算类权重） | **2.822 s** | 惰性加载成本 |
| 第 1 次 `detect()` | **0.609 s** | 含首次 CUDA 上下文/算子预热 |
| 第 2 / 3 次 `detect()` | **0.013 s** | 稳态 |
| 第 1 / 2 次 `generate_cam()`（热力图） | **0.090 s / 0.037 s** | 热力图路径冷启动代价仅约 50 ms，可忽略 |
| **端到端：子进程启动 → `/health` 200** | **4.884 s** | |
| **端到端：首个 `/predict` 成功返回** | **3.472 s**（HTTP 200, `ok=true`, 返回 `heatmap_url`） | |
| 第 2 / 3 次 `/predict` | **0.083 s / 0.074 s** | |
| 非图片上传（`.txt`） | 0.047 s，HTTP 200 + `ok=false`「无法读取图片」 | 不会 500 |

**结论 1**：**进程启动到第一次出结果，实测约 8.4 s**（4.884 + 3.472）。这**不是**"首次请求卡 30 秒"，任务书里担心的 30 秒来自 LLM 超时路径，与模型冷启动无关（见 B2 第 7 条）。8.4 s 在演示中偏长但可接受。

**结论 2**：团队已在 `main.py` 的 `on_startup` 里做了**启动期预热**（`ensure_dirs()` → `gc_uploads_throttled()` → `detector.load()` → `_prime_forward()`），把上述 2.8 s 加载 + 0.6 s 首次前向挪到无人观察的启动阶段。**复核通过**：这正是"演示前必须预热"的正确落地方式。

**结论 3（必须落实的操作纪律）**：本次实测的 CUDA 上下文是**驱动热态**（桌面已常驻占用 1.5GB 显存）。**机器刚开机、驱动冷启时，首次 CUDA 上下文创建可显著更慢**。因此：

- 演示当天**必须**在评委到来前**提前双击 `run.bat` 并完成一次"上传示例图 → 看到结果"的完整热身**，然后**保持该进程不关**。不要等到评委面前才第一次启动。
- 现场若被要求重启服务，重启后**先自己跑一张示例图**，确认出图后再交给评委操作。
- 可选加固：给服务加一个 `/warmup` 端点（幂等、立即返回）供外部脚本在开场前调用；现有启动期预热已覆盖，属于锦上添花。

### B2. 断网可用性：所有外部网络调用路径与离线封堵

**先在源码层面核实 ultralytics 8.4.137 到底支持哪些离线环境变量**（实测，非凭印象）：

| 环境变量 | 是否被 ultralytics 引用 | 实测效果 | 位置 |
|---|---|---|---|
| `YOLO_OFFLINE` | **是**（唯一真正生效的离线开关） | 设为 `1/true` → `ONLINE=False` | `ultralytics/utils/__init__.py` `is_online()` line 865 |
| `ULTRALYTICS_OFFLINE` | **否（0 处引用）** | 设为 `1` 后 `ONLINE` 仍为 `True` —— **无效** | 全包 grep 命中 0 |
| `YOLO_VERBOSE` | 是 | 控制详细日志 | `ultralytics/utils/__init__.py` |
| `YOLO_CONFIG_DIR` | 是 | 控制 settings.json 位置 | `ultralytics/utils/__init__.py` line 961 |

实测对照：
- `YOLO_OFFLINE=1` → `ultralytics.utils.ONLINE == False`
- `ULTRALYTICS_OFFLINE=1` → `ultralytics.utils.ONLINE == True`（**设了没用**）
- 先 `import app.config` 再 `import ultralytics.utils` → `ONLINE == False`（config 的 `setdefault` 抢在 ultralytics import 之前）
- 先 `import ultralytics.utils` 再设 → `ONLINE == True`（**依赖 import 顺序**）

**网络路径清单与封堵**

| # | 路径 | 触发条件 | 是否在 `/predict` 路径上 | 离线封堵 |
|---|---|---|---|---|
| 1 | `is_online()` → DNS 解析 `one.one.one.one` / `dns.google` | **每次 `import ultralytics`** | 是（indirect） | `YOLO_OFFLINE=true`（实测生效）。已由 `run.bat` 与 `config.py` 双设 |
| 2 | `check_pip_update_available()` → `GET https://pypi.org/pypi/ultralytics/json` | 仅 `model.train()` | 否 | `YOLO_OFFLINE=true` 即短路（`if ONLINE and IS_PIP_PACKAGE`） |
| 3 | `check_amp()` → 下载 `yolo26n.pt`（GitHub） | 仅训练（`trainer.py`） | 否 | 训练时才相关；离线训练需预置该权重或跳过 AMP |
| 4 | `check_font()` → 下载 `Arial.ttf`/`Arial.Unicode.ttf` | 仅绘图（`plotting.py`、`data/utils.py`） | 否（`main.py` 不调用 `results.plot()`） | 无 |
| 5 | `YOLO("yolo11n.pt")` 兜底 → `attempt_download_asset`（GitHub） | 仅当生产权重缺失 | 否（已改） | **团队已修**：`resolve_model_path()` 在两者都缺时抛 `FileNotFoundError`，不再触发下载 |
| 6 | Sentry（`set_sentry`） | 需 `argv[0]` 名称为 `yolo` 且 `sync=True` 且联网 | 否（入口是 python/uvicorn） | 天然不触发；如需彻底关闭可 `SETTINGS["sync"]=False` |
| 7 | `requests.post` → DashScope（LLM 处方） | `LLM_ENABLED=True` | **是** | 占位符防护 + 双段超时 `(3.5s, 12s)`。**断网时最坏约 15.5 s 后回落模板** |
| 8 | `downloads.safe_download` 内部的 `is_online()` 检查 | 任何下载动作 | 否 | 同上 |

**对任务书关注点的明确回答**：
- `FALLBACK_MODEL="yolo11n.pt"` 这条隐患：**已消除**（改为 `models/yolo11n-cls.pt` + `resolve_model_path()` 抛错），不再会因缺权重去 GitHub 拉模型；同时也修掉了一个更严重的原始缺陷 —— 原兜底是**检测**模型 `yolo11n.pt`，而 `detector.load()` 会无条件访问分类头独有的 `.conv`，缺失 `best.pt` 时**启动即崩**（`AttributeError: 'Detect' object has no attribute 'conv'`）。
- AMP 检查下载 `yolo26n.pt`：**仅在训练路径**，推理不受影响。
- telemetry / 更新检查：只有 `YOLO_OFFLINE` 这一条开关真正管用；`ULTRALYTICS_OFFLINE` 是**无效变量**，不要再依赖它。

**待办（1 条）**：`run.bat` 与 `config.py` 里都设了 `ULTRALYTICS_OFFLINE=true`，属无效设置，建议删除以免"以为已双保险"。

### B3. 失败降级矩阵

| 故障点 | 期望行为 | 用户看到什么 | 兜底实现（位置 / 现状） |
|---|---|---|---|
| 无 GPU / CUDA 不可用 | 服务仍可用，降级 CPU 推理 | 结果正常，只是慢（实测 CPU 下 detect 数量级上升）；`/api/v1/meta` 的 `device` 显示 cpu | 模型加载不显式 `.to(cuda)`，由 ultralytics 自动选设备；**未做显式 CPU 分支断言**（见 `advisory` A-6） |
| 显存不足（本机仅 6GB，桌面已占 1.5GB） | 不崩服务 | 单次请求返回 `ok=false` + "识别过程出现异常，请重试。" | `_run_predict` 第 4 步 `try/except` 包住推理段（`main.py` line 302–326）；**建议**演示前关掉 Edge/微信/VS Code 释放显存 |
| 模型文件缺失（`best.pt`） | 启动期显式暴露，不留到首个请求 | 以 `yolo11n-cls.pt` 兜底；两者都缺则启动日志报"未找到可用模型权重，服务将以不可用状态运行" | `config.resolve_model_path()` 抛 `FileNotFoundError`；`on_startup` 捕获并记日志；**`run.bat` 建议改为拒绝启动**（A4） |
| `.env` 未配置或为占位符 | 完全可用，处方走模板，不发网络请求 | 处方正常显示，`prescription_source="template"` | `config._read_llm_key()` 占位符 + 长度双判（line 53–63） |
| LLM 超时 | 按时返回，不挂起 | 处方仍显示（模板），`prescription_source="template"` | 双段超时 `(3.5, 12)` + `except` 回落（`prescriber.py` line 116–125） |
| LLM 返回非法 JSON / 围栏包裹 | 回落到模板 | 同上 | `_strip_fence` + 字段完整性校验（`prescriber.py` line 55–58、139–149） |
| 热力图生成失败 | 返回识别结果，只是没有热力图 | 结果正常，热力图区域为空（前端需容错） | `generate_cam` 内部 `try/except → None`；`main.py` 仅在有值时才带 `heatmap_url`（line 316–323） |
| `uploads/` 不存在或不可写 | 服务仍能启动 | 正常 | `main.py` 在 `app.mount` **之前**调用 `ensure_dirs()`（line 194）—— 这是关键修复：`StaticFiles` 在 mount 时会立刻检查目录存在，缺目录会抛 `RuntimeError` 令整个应用无法启动 |
| 上传非图片 / 超大图 | 明确拒绝，不 500 | 200 + `ok=false` + 中文原因 | `_read_limited(max=MAX_UPLOAD_BYTES)` 分块早停 + `imaging.validate_upload`（扩展名白名单 + 魔数）；实测非图片返回 200/`ok=false` |
| 端口 8000 被占用 | 启动前拦截 | `run.bat` 打印占用提示并暂停 | `netstat + findstr` 检查；uvicorn 侧随后仍会报错，双层 |
| `.env` 误暴露（`serve_panel.bat`） | 不再存在该角色 | — | 脚本已删除并移入备份（A4） |

### B4. 演示前检查清单（可直接交给学生照做）

> 全部用 PowerShell。**bash 在本机不可用**；PowerShell 原生命令输出不回传，若需留证请重定向到文件再查看。

**T-30 分钟**

1. 关闭占用显存的程序（实测桌面常占约 1.5GB / 共 6.1GB）：Edge、微信、VS Code、剪映等。
   ```powershell
   nvidia-smi      # 期望 Memory-Usage 里本机占用显著下降，先看 "1543MiB / 6141MiB" 是否变小
   ```
2. 确认环境与权重：
   ```powershell
   cd D:\shuangti11\ICAN\ican\CNDS
   .venv\Scripts\python.exe -c "import torch,ultralytics,cv2,numpy;print(torch.__version__,torch.cuda.is_available(),ultralytics.__version__,cv2.__version__,numpy.__version__)"
   # 期望：2.13.0+cu126 True 8.4.137 5.0.0.93 2.5.3
   Get-Item models\best.pt | Select-Object Length   # 期望 3281538
   ```
3. 断网自检（可选，但强烈建议在断网状态下做一次）：拔网线/关 Wi-Fi，重复第 4–6 步，确认全程无卡顿。

**T-15 分钟**

4. 启动服务：
   ```powershell
   .\run.bat
   # 期望：窗口标题含 "禾目 AgriGuard"；出现 "模型预热完成，耗时 x.xx s"；无红色报错
   ```
5. 健康检查（另开一个 PowerShell 窗口）：
   ```powershell
   curl.exe -s http://127.0.0.1:8000/health
   # 期望：{"status":"ok","model_ready":true}
   ```
6. **热身（关键，不要跳过）**：浏览器打开 `http://127.0.0.1:8000`，点"上传示例病叶图"，看到「番茄 · 早疫病」+ 热力图。**实测首个请求约 3.5 s，之后约 0.08 s** —— 现场必须让"慢的那一次"发生在评委来之前。

**T-5 分钟**

7. 确认不要误建 `.env`：若存在 `.env`，确认里面的 `LLM_API_KEY` 是**真密钥**；若是占位符 `sk-your-key-here`，程序会自动走模板（不会卡超时），但答辩口径要按"模板处方"讲。
   ```powershell
   Test-Path .env      # True 则检查内容；False 则走模板，属正常
   ```
8. 浏览器**只保留**产品页一个标签；关闭自动更新/通知弹窗；把浏览器缩放调到评委可读。
9. 保持服务进程**不关**，直到评审结束。

**现场若出问题（30 秒恢复动作）**

| 现象 | 动作 |
|---|---|
| 页面打不开 | 回 PowerShell 看服务窗口是否还在；按 Ctrl+C 后重新 `. \run.bat`，再热身一张图 |
| 上传报"服务内部异常" | 关掉占显存的程序，重试一次 |
| 端口被占 | `netstat -ano | findstr :8000`，结束占用进程或改 `run.bat` 端口 |
| 网络异常 | 无需处理 —— 本服务除 LLM 外全部本地；直接走模板处方 |

### B5. 备份与回滚方案（PowerShell，配合"清理 7GB + 重组结构"）

**现状说明**：任务书中的"即将清理 7GB"**已被团队执行完毕**。实测 `data/` 已从 7.9GB 降到 892.8MB，`downloads/`、`plantvillage_combined/`、`plantvillage_balanced/`、`datasets_raw/` 均已不存在；同时已存在一份备份目录 `.workbuddy\backup\2026-09-20\`（含 8 个根目录废弃产物）。因此本节给出的是**可复用的低风险执行序**（供后续任何清理/重组沿用），以及**对已完成清理的补强动作**。

**低风险执行序（PowerShell，四步）**

```powershell
# ---- 步骤 1：先确认版本控制干净（回滚的底气来自 git，不是文件副本）----
cd D:\shuangti11\ICAN\ican\CNDS
git status --porcelain          # 必须为空（或只有本次审计的临时文件）
git log --oneline -n 5          # 记下当前 HEAD，作为回滚锚点

# ---- 步骤 2：备份到版本控制之外的位置（不要放在被清理的目录里）----
$stamp = "2026-09-20"
$bk = "D:\shuangti11\ICAN\ican\CNDS\.workbuddy\backup\$stamp"
New-Item -ItemType Directory -Path $bk -Force | Out-Null

# 2a) 待清理项：先"移动"而不是"删除"（可秒级回滚）
$targets = @("models\best_old.pt", "serve_panel.bat", "status.json", "进度面板.html",
             "download.js", "progress.js", "uploads_analysis.json", "项目审查报告.html")
foreach ($t in $targets) { if (Test-Path $t) { Move-Item -LiteralPath $t -Destination $bk -Force } }

# 2b) 大体积数据：用压缩归档保留"可还原"能力（若不打算再训练可跳过）
#     注意 data\plantvillage 必须保留 —— 它是唯一训练集，删了就无法离线重训
$keep = "data\plantvillage"
if (Test-Path "data\downloads") {
    Compress-Archive -Path "data\downloads", "data\plantvillage_combined",
                            "data\plantvillage_balanced", "data\datasets_raw" `
                     -DestinationPath "$bk\data_redundant_$stamp.zip" -CompressionLevel Optimal -Force
}

# ---- 步骤 3：验证备份完整（关键：比对文件数与字节数）----
$src = @("data\downloads", "data\plantvillage_combined", "data\plantvillage_balanced", "data\datasets_raw")
$srcN = 0; $srcB = 0
foreach ($s in $src) { if (Test-Path $s) {
    $m = Get-ChildItem $s -Recurse -File | Measure-Object -Property Length -Sum
    $srcN += $m.Count; $srcB += $m.Sum } }
"源：$srcN 文件 / $([math]::Round($srcB/1MB,1)) MB"

# 解压到临时目录做一次"真还原"验证（比只看 zip 大小可靠）
$verify = "$bk\_verify_extract"
Remove-Item $verify -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path "$bk\data_redundant_$stamp.zip" -DestinationPath $verify -Force
$v = Get-ChildItem $verify -Recurse -File | Measure-Object -Property Length -Sum
"还原：$($v.Count) 文件 / $([math]::Round($v.Sum/1MB,1)) MB"
# 期望：文件数与字节数一致（压缩只改体积不改内容计数）

# ---- 步骤 4：确认无误后再删除源（不可逆动作放最后）----
# 先确认 plantvillage 还在：
Get-Item "data\plantvillage" | Select-Object FullName
foreach ($s in $src) { if (Test-Path $s) { Remove-Item $s -Recurse -Force } }
```

**回滚方法**

```powershell
# 情形 A：只是文件被误移/误删（备份目录还在）
$bk = "D:\shuangti11\ICAN\ican\CNDS\.workbuddy\backup\2026-09-20"
Move-Item "$bk\*" -Destination "D:\shuangti11\ICAN\ican\CNDS" -Force   # 逐个确认后再执行

# 情形 B：代码被改坏（git 有历史）
cd D:\shuangti11\ICAN\ican\CNDS
git status                                  # 看动了什么
git restore <被改坏的文件>                   # 单文件回滚
git stash                                   # 或先把当前改动暂存再回滚
git checkout <HEAD 锚点> -- backend/         # 按目录回滚

# 情形 C：大体积数据要还原
Expand-Archive "$bk\data_redundant_2026-09-20.zip" -DestinationPath "D:\shuangti11\ICAN\ican\CNDS\data" -Force
```

**清理对可复现性的影响评估（回答任务书第 9 问）**

| 已删内容 | 将来重训是否需要 | 依据 |
|---|---|---|
| `data/downloads/*.zip`（6.49GB） | **不需要保留在本地**，但**需要能重新下载** | `scripts/organize_plantvillage.py` 从 zip 解压整理；`scripts/download_extra_datasets.py` 可从 **ModelScope `OmniData/PlantVillage`**（增强版约 949MB / 原始版约 868MB）重新拉取，支持断点续传 |
| `data/plantvillage_combined/`（497MB） | 不需要 | 中间产物，已弃用 |
| `data/plantvillage_balanced/`（26MB） | 不需要 | `scripts/train_v2.py --balance` 会按需**重新生成** `data/plantvillage_balanced/` |
| `data/datasets_raw/`（10.2MB） | 不需要 | 原始碎片 |
| `data/plantvillage/`（892.8MB） | **必须保留** | 唯一训练集，`train_v2.py` 的默认 `--data data/plantvillage`；删了就**无法离线重训** |

**两个补强动作（建议）**
1. `data/` 整体在 `.gitignore` 里，训练集**无法从版本控制恢复**。建议把"数据集来源 + 复现命令"落到**会被 git 跟踪**的文档里（如 `docs/数据复现.md`，内容：ModelScope `OmniData/PlantVillage`、`download_extra_datasets.py` → `organize_plantvillage.py` → `train_v2.py` 三步命令、期望 38 类 / train 48282 / val 12061）。这样即使本机数据丢失，也能凭仓库文档重建。
2. 备份保留期建议 ≥ 覆盖到国赛结束（`data` 类归档可 30 天，`models\best_old.pt` 等小文件建议留到国赛结束）。

### 附：任务书第 10 问（12 个孤儿素材脚本）

实测 `scripts/` 35 个文件，其中 12 个素材生产脚本的输入输出 `media/` 目录确实已不存在：`build_pptx.py`、`build_video2.py`、`build_demo_video.py`、`build_poster.py`、`build_devlog.py`、`build_supporting.py`、`ppt_assets.py`、`narrate.py`、`narration.py`、`_tts_test.py`、`_preview2.py`、`regenerate_heatmap.py`、`analyze_uploads.py`、`make_demo_compliant.py`、`build_extra_assets.py`。

处置建议：**保留在版本控制，不删除**。理由：这些脚本的**产物是参赛物料**，评审/答辩若被要求补充材料（宣传视频、海报、开发日志），重新生产的成本远高于保留 0.15MB 源码的成本。可选优化：把它们移入 `scripts/materials/` 子目录并在 README 标注"产物依赖 media/，当前 media/ 已不存在"。**不建议**为了"仓库整洁"删掉——这是一个纯收益为负的清理。

---

## C. 面向验收的可核查结论

```yaml
verdict: fail

blocking:
  - 违反项: 需求未满足 —— 干净机器从零复现失败（setup.bat CUDA 分支无法装到实测的 CUDA 版 torch）
    证据: >
      E1. mirrors.aliyun.com/pytorch-wheels/cu126/ 是"扁平 wheel 目录"（HTML 里 1298 个 .whl 直链），
          不是 PEP503 简单索引；pip 用 --index-url 时会请求 .../cu126/torch/，
          实测该 URL 返回 HTTP 404（.../cu126/torchvision/ 同为 404）。
      E2. 因此 setup.bat 的 CUDA 分支拿不到该目录下的 wheel，只能从
          --extra-index-url https://mirrors.aliyun.com/pypi/simple/ 解析；
          该索引上的 torch 2.13.0 是"无本地版本号"的 torch-2.13.0-cp313-cp313-win_amd64.whl。
      E3. 本机实测环境是 torch 2.13.0+cu126 / torchvision 0.28.0+cu126，
          且 pytorch-wheels/cu126/ 目录里确实存在 torch-2.13.0+cu126-cp313-cp313-win_amd64.whl
          —— 说明实测环境来自 find-links 索引（-f），而不是 PyPI 索引（原版 setup.bat 用的就是 -f + +cu121）。
      E4. 新版 setup.bat 丢掉了 -f 与 +cu126 本地版本号，未能在本机完成 pip --dry-run 端到端验证
          （工具链不稳，见"未验证项"）；但 E1+E2 已足以证明该命令无法从目标索引取包。
    期望: >
      setup.bat 的 CUDA 分支改为：torch==2.13.0+cu126 / torchvision==0.28.0+cu126
      + -f https://mirrors.aliyun.com/pytorch-wheels/cu126/ + -i .../pypi/simple/，
      并在装完后断言 torch.cuda.is_available() 为真（失败即报错退出）。

advisory:
  - 建议项: run.bat / config.py 里的 ULTRALYTICS_OFFLINE=true 是无效变量
    理由: 全包 grep 命中 0；实测设该变量后 ultralytics.utils.ONLINE 仍为 True（唯一生效的是 YOLO_OFFLINE）。留着会造成"已双保险"的错觉。
  - 建议项: .env.example 的 LLM_ENABLED 是"无效开关"
    理由: config.py 从不读该变量（LLM_ENABLED 由密钥有效性推导）。用户写 false 期望关闭时不会生效，属文档与实现语义不一致。
  - 建议项: requirements-train.txt 里的 polars 应删除
    理由: 全项目 *.py grep 引用数 0，属"装了不用"，只增加安装失败面。
  - 建议项: psutil（实测 7.2.2）无任何代码引用
    理由: 原为已废弃进度面板所用；不进任何 requirements，交付环境也不应包含。
  - 建议项: 模型权重入库（models/best.pt 3.28MB + models/yolo11n-cls.pt 5.79MB）
    理由: 二进制权重会让 .git 体积随时间膨胀。若坚持"交付包自包含"可保留，但建议明确这是有意为之，并考虑改用 release/网盘分发。
  - 建议项: run.bat 缺窗口标题、且模型缺失时仅警告后继续
    理由: 多窗口演示时标题是硬需求；用兜底权重出结果去演示比服务起不来更危险，建议改为拒绝启动。
  - 建议项: 测试/可观测维度仅 Bronze（总档被拉低）
    理由: 无 pytest、无 CI、无指标/告警；verify_pipeline.py 与 smoke_test.py 属人肉脚本。见下方记分卡。
  - 建议项: data/*.gitignore 使训练集无法从版本控制恢复
    理由: 建议把"数据集来源 + 三步复现命令"写入被跟踪的 docs/数据复现.md。

evidence:
  - artifact_ref: 实测命令输出（本次审计，见 .workbuddy/review/ 下 devops_* 文件）
    line: §0 表
    说明: python 3.13.14 / torch 2.13.0+cu126 / ultralytics 8.4.137 / numpy 2.5.3 / opencv 5.0.0.93；
          GPU=RTX 4050 Laptop 6141MiB（非 4060/8GB），驱动 590.26，CUDA 12.9（非 592.00/13.1）
  - artifact_ref: D:\shuangti11\ICAN\ican\CNDS\setup.bat
    line: 70-72
    说明: CUDA 分支用 --index-url 指向扁平 wheel 目录并 pin torch==2.13.0（无 +cu126）
  - artifact_ref: 实测 URL 探测（devops_probe2.json）
    line: -
    说明: mirrors.aliyun.com/pytorch-wheels/cu126/torch/ → 404；.../cu126/ → 200（1298 个 whl）
  - artifact_ref: setup.bat 原版（git d5b8053 之前的工作区版本，见任务书/交接文档）
    line: 交接文档 356-359
    说明: 原版为 -f https://mirrors.aliyun.com/pytorch-wheels/cu121/ + torch==2.5.1+cu121，参数形态正确（仅版本号过期）
  - artifact_ref: D:\shuangti11\ICAN\ican\CNDS\.venv\Lib\site-packages\ultralytics\utils\__init__.py
    line: 865, 997
    说明: is_online() 读取 YOLO_OFFLINE；ONLINE = is_online() 在 import 期求值。ULTRALYTICS_OFFLINE 全包无引用
  - artifact_ref: D:\shuangti11\ICAN\ican\CNDS\backend\app\config.py
    line: 21-108
    说明: load_dotenv 替换手写解析；占位符防护 _PLACEHOLDER_MARKERS；LLM_ENABLED 由密钥推导（不读同名环境变量）；ensure_dirs 只建 MODELS_DIR/UPLOAD_DIR
  - artifact_ref: D:\shuangti11\ICAN\ican\CNDS\backend\app\main.py
    line: 194, 135-182, 302-326, 395-410
    说明: mount 前 ensure_dirs（修 StaticFiles 因缺目录启动失败）；on_startup 预加载；推理段 try/except + 统一 JSON 异常；def 而非 async def（避免堵事件循环）
  - artifact_ref: 实测 git 检查（devops_git.txt / devops_git2.txt）
    line: -
    说明: 3 次提交 / 81 个跟踪文件；.env、.venv/、data/*、uploads/*、runs/**/weights/ 均被正确忽略；
          runs/agriguard_v2 的 results.csv|png|confusion_matrix 已纳入；跟踪文件内无真实密钥（仅占位符 sk-your-key-here）
  - artifact_ref: 实测尺寸（devops_sizes.json）
    line: -
    说明: data 892.8MB/60177（仅 plantvillage）；downloads|combined|balanced|datasets_raw 已不存在；uploads 0.2MB/14；runs 9.1MB/17；.venv 4574.1MB
  - artifact_ref: 冷启动实测（_out_coldstart.json）
    line: -
    说明: import app.main 3.097s；detector.load 2.822s；首次 detect 0.609s；稳态 0.013s；
          HTTP：health 4.884s、首个 /predict 3.472s（200/ok=true/有 heatmap_url）、第二 0.083s、非图片 0.047s（200/ok=false）
```

**未验证项（明确标注，不含猜测）**

| 项 | 未验证内容 | 验证方法 |
|---|---|---|
| U1 | aliyun PyPI 镜像上**无本地版本号**的 `torch-2.13.0-cp313-cp313-win_amd64.whl` 是否自带 CUDA | 建一个一次性 venv 执行 `pip install "torch==2.13.0" -i https://mirrors.aliyun.com/pypi/simple/`，再 `python -c "import torch;print(torch.version.cuda, torch.cuda.is_available())"`。**注**：即使该 wheel 自带 CUDA，能复现的也只是"某版 CUDA 的 torch"，与实测的 `+cu126` 不是同一个构建，仍不满足"复现实测环境" |
| U2 | 新版 `setup.bat` CUDA 分支的 pip 端到端解析结果 | 在一次性 venv 执行原命令加 `--dry-run --report -`，读 JSON 里的 `download_info.url`。本次尝试因工具链不稳定未能完成 |
| U3 | 驱动冷启（重启后首次）的 CUDA 上下文初始化开销 | 重启机器后立刻计时"启动服务 → 首个 /predict 返回"，与本次热态 8.4s 对比 |
| U4 | CPU 分支实际安装到的 torch/torchvision 组合是否与 ultralytics 8.4.137 兼容 | 在无 GPU 环境执行 CPU 分支后跑 `scripts/verify_pipeline.py` |

---

## D. 生产就绪记分卡评级（对照 `references/01-standards/production-readiness-scorecard.md`）

基准：本作品为**本机离线演示型**应用（无端用户、无多租户）。团队目标档按知识库"商业级最低 Silver"。**总档取各维最低档。**

| 维度 | 当前档位 | 依据 |
|---|---|---|
| 测试 + 回归 | **Bronze** | `scripts/verify_pipeline.py` 5/5、`smoke_test.py` 可跑，核心流有测试；但无 pytest、无 CI、回归集未进门禁 |
| 契约 | **Silver** | `/api/v1/meta` 统一下发阈值真值，前后端不再硬编码双份；统一异常处理器返回同构 JSON。缺版本与弃用策略闭环，故止步 Silver |
| 安全 | **Bronze** | 输入校验（体积上限 + 扩展名白名单 + 魔数）、存储型 XSS 已修、CORS 收敛、密钥不入库（实测）；无鉴权/无限额（本机单用户形态下不适用），依赖存在性核验仅靠 pin |
| 无障碍 | **未评估** | 属前端同事范围；本次未做键盘可达/对比度/语义核查 |
| 性能 | **Silver** | 稳态请求 0.08s、启动期预热消除首点延迟、大图已做边长收敛、响应带 `latency_ms`；无容量/压测验证 |
| 可观测 | **Bronze** | 结构化日志（时间/级别/logger/消息）+ `/health` 带 `model_ready` + 请求带 `latency_ms`；无指标、无 SLI/SLO、无告警 |
| 发布安全 | **Bronze** | 可回退（git 3 次提交 + `.workbuddy\backup\2026-09-20\` + 本报告 B5 执行序）；无渐进发布、未做回滚演练 |

**总档：Bronze（未达商业级 Silver）** —— 短板维度为：测试+回归、安全、可观测、发布安全（无障碍未评估）。

**补到 Silver 的最小动作（按性价比排序）**
1. 测试+回归：把 `scripts/verify_pipeline.py` 与 `smoke_test.py` 落成 `tests/` 下的 pytest 用例，并在 `run.bat`/CI 前跑一次（回归率归零 → 进"门禁"）。
2. 可观测：在 `/health` 基础上加一个 `/metrics`（请求数、失败数、p95 延迟、OOD 拒识率），演示时可用它自证"现场零故障"。
3. 发布安全：把 B5 的回滚执行序**真的演练一次**并留档（截图/日志），从"能回退"升到"回滚预案演练过"。
4. 安全：为 `/predict` 加简单令牌或仅监听 127.0.0.1（现已是 127.0.0.1）+ 上传体积上限（已有）合并计入输入校验闭环。
5. 无障碍：由前端同事补键盘可达与对比度核查（≥AA）。

---

## E. 审计后追加：修复落地复核与归属记录

> 本节在首版报告（15:25:47 落盘）之后追加。目的：让评审能对上"谁改的、改了什么、谁复核的"。

### E1. 归属记录（避免评审时对不上）

- 本审计**未修改任何项目代码或脚本**，全部写入仅在 `.workbuddy\review\`。
- 报告落盘后，**另有同事依据本报告完成落盘并代为提交**，提交 `eaa4209`，提交信息为「修正 CUDA 安装分支静默退化为 CPU 版；清理无效开关；并入运维维度审查」。
- 相关文件落盘时间（均晚于本报告 15:25:47）：`setup.bat` 15:26:37、`config.py` 15:26:46、`run.bat` 15:26:58、`.env.example` 15:27:11。
- 更早一轮（14:53–14:54：`requirements.txt` / `setup.bat` / `run.bat` / `.env.example` / `.gitignore`）发生在本审计开始之前，亦非本审计所为。
- `git status --porcelain` 对项目文件为空（工作区干净）。

### E2. 修复复核结果（逐条读文件复核，非采信转述）

| 项 | 状态 | 复核依据 |
|---|---|---|
| B-1（blocking）setup.bat CUDA 分支 | **已修复** | `setup.bat` line 72–99：改用 `-f https://mirrors.aliyun.com/pytorch-wheels/cu126/` + `torch==2.13.0+cu126` / `torchvision==0.28.0+cu126`；分支内新增 CUDA 硬断言，失败即 `exit /b 1`，注释明确写出"pip 成功 ≠ 装到 CUDA 版"。与本报告 §C 的期望完全一致 |
| A-1 `ULTRALYTICS_OFFLINE` 无效开关 | **已修复** | `config.py` line 95–102：已无任何 set 调用，仅保留解释性注释（并注明"若升级 ultralytics 请重新核实生效开关名"）；全仓 grep 无 set |
| A-2 `LLM_ENABLED` 无效开关 | **已修复** | `config.py` line 77–93：新增 `_read_llm_switch()`（仅 `0/false/no/off` 关闭），`LLM_ENABLED = _read_llm_switch() and bool(LLM_API_KEY)`，语义与期望一致 |
| A-3 `.env.example` 与实现对齐 | **已修复** | `.env.example` 已改写为新语义（显式关闭的取值 + "无有效 key 时不发请求"） |
| A-4 run.bat 窗口标题 / 模型缺失处置 | **已修复** | `run.bat` 15:26:58 重写（未逐字复核，属建议级别） |

### E3. 残留小项（非阻塞）：解释器探测链 —— **本机缺口已闭合，他机由文档兜住**

**第一层（已修复）**：`setup.bat` 原先把 `py -3.12` 排在 `py -3.13` 之前。现已改为**五段探测链**（`setup.bat` line 33–63），每段都有 `PYDESC` 标注：

| 顺位 | 探测目标 | 说明 |
|---|---|---|
| (a) | `%AGRI_PYTHON%` | 环境变量显式指定（校验存在 + `import sys` 成功），换机器时最可靠 |
| (b) | `py -3.13` | 标注"本项目已验证的主版本" |
| (c) | `%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe` | 已知独立分发解释器（验证环境实际来源） |
| (d) | `py -3.12` | 标注"**未验证路径**，建议改用 3.13" |
| (e) | `python` | 标注"版本未确认" |

**第二层（实测复核 + 更正我前一轮的结论）**：本机 `py` 启动器确实**未注册 3.13**：

```
py -0p
 -V:3.14 *        C:\Users\weizunhao\AppData\Local\Programs\Python\Python314\python.exe
 -V:3.12          C:\Users\weizunhao\AppData\Local\Programs\Python\Python312\python.exe
 -V:3.11          D:\python.exe

py -3.13 -c "import sys"   →  rc = -1610612730（No runtime installed that matches 3.13）
py -3.12 --version         →  Python 3.12.10
py -3.14 --version         →  Python 3.14.7
（(c) 路径）--version       →  Python 3.13.14      Test-Path = True，rc = 0
```

**更正**：由于新增了 (c) 这条独立解释器探测，**本机 fresh 跑 `setup.bat` 会命中 (c) → 3.13.14（已验证路径），不再落到 3.12**。实测复核：(c) 的 `Test-Path = True`、`--version` = `Python 3.13.14`、rc = 0；(b) 实测失败。→ **本机的复现缺口已被 (c) 补上**，我前一轮"本机仍落 3.12"的判断据此作废。

**残留限制（固有限制，不是缺陷）**：仅当一台机器**三者同时不成立** —— 未设 `AGRI_PYTHON`、launcher 无 3.13、且不存在该独立解释器 —— 才会落到 (d) 3.12（未验证路径）。此限制**已由 `docs/数据复现.md` 兜住**（实测存在，7,687 bytes）：该文档 §1.0 写明 py/3.13 这个坑、`AGRI_PYTHON` 用法、以及"目录名是 3.13.12 但解释器实际报告 3.13.14，勿以目录名为准"；并给出 3.12 路径的处置（能装能跑，但必须补跑 `scripts/verify_pipeline.py` 再用于演示）。

**对交付口径的影响（相比前一轮已放宽）**：本机"重装即可复现验证环境"**现在成立**（因为 (c) 生效）。正确口径是**有条件表述**：
- 本机 / 具备该独立解释器的机器：fresh `setup.bat` → 3.13.14 验证环境，可 1:1 复现；
- 其他机器：用 `set AGRI_PYTHON=<python313 路径>` 指定，或接受 3.12 并补跑回归。
**不建议**写成无条件的"任何机器重装即可 1:1 复现"。

**为何仍判非阻塞**（结论不变）：`https://mirrors.aliyun.com/pytorch-wheels/cu126/`（共 1298 个 whl）同时提供 cp312 与 cp313 的 Windows wheel，3.12 路径**能装能跑**：
`torch-2.13.0+cu126-cp312-cp312-win_amd64.whl`、`torch-2.13.0+cu126-cp313-cp313-win_amd64.whl`、
`torchvision-0.28.0+cu126-cp312-cp312-win_amd64.whl`、`torchvision-0.28.0+cu126-cp313-cp313-win_amd64.whl`。
故属"验证覆盖"缺口，而非"装不上/跑不起来"。

### E4. 遗留的未验证项（承 §C）

U1–U4 仍成立。其中 U1（aliyun PyPI 上无本地版本号的 `torch-2.13.0` 是否自带 CUDA）**已失去实际意义**：修复后 setup.bat 不再走该回落路径，只从 `-f .../cu126/` 取带 `+cu126` 的构建。

---

## 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-09-20 | 首次生成 | 运维审计：依赖可复现性 + 部署/现场演示健壮性 |
| 2026-09-20 | 追加 §E | 修复落地复核、归属记录、残留小项（Python 3.12/3.13 优先级） |
| 2026-09-20 | §E3 二次修订 | 复核 setup.bat 五段探测链 (a)–(e)；更正"本机仍落 3.12"的判断——(c) 已闭合本机缺口，他机由 docs/数据复现.md + AGRI_PYTHON 兜住 |
