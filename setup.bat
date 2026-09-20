@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   禾目 AgriGuard - 运行环境安装
echo ============================================================
echo.
echo  说明：本脚本会创建 .venv 并安装依赖。
echo        若 .venv 已存在且可正常导入 torch，建议直接跳到 run.bat。
echo.
echo  请选择 PyTorch 版本：
echo    [1] CUDA 12.6（推荐；需 NVIDIA 显卡且驱动版本 ^>= 525）
echo    [2] CPU 版（无独立显卡，或只做接口联调）
echo.
set "CHOICE="
set /p CHOICE=请输入 1 或 2 后回车（直接回车默认 1）: 
if "%CHOICE%"=="" set "CHOICE=1"

REM ---- 1. 定位可用的 Python ----
echo.
echo [1/5] 检查 Python ...
REM 优先 3.13：本项目的 .venv 与全部验证（含回归 5/5）均在 Python 3.13.14 上完成。
REM 3.12 也能装（cu126 索引同时提供 cp312 / cp313 的 Windows wheel），
REM 但 3.12 这套组合**从未跑过 scripts\verify_pipeline.py**，属未验证路径。
REM
REM 探测顺序说明（实测教训，别改成只靠 py -3.13）：
REM   Windows 的 py 启动器**不一定注册了 3.13** —— 本机实测 py -0p 只有 3.14/3.12/3.11，
REM   而已验证的 3.13.14 解释器是独立分发的、不在启动器注册表里。
REM   因此只用 `py -3.13` 会探测不到并静默落回 3.12，装出未验证的环境。
REM   所以这里额外探测已知的独立解释器路径，并支持用环境变量 AGRI_PYTHON 显式指定。
set "PYCMD="
set "PYDESC="

REM (a) 环境变量显式指定优先（换机器时最可靠的指定方式）
if defined AGRI_PYTHON (
    if exist "%AGRI_PYTHON%" (
        "%AGRI_PYTHON%" -c "import sys" >nul 2>&1 && set "PYCMD=%AGRI_PYTHON%"
        if defined PYCMD set "PYDESC=由环境变量 AGRI_PYTHON 指定"
    )
)

REM (b) py 启动器 3.13
if not defined PYCMD py -3.13 -c "import sys" >nul 2>&1 && set "PYCMD=py -3.13"
if not defined PYDESC if defined PYCMD set "PYDESC=3.13（本项目已验证的主版本）"

REM (c) 已知的独立分发解释器路径。
REM     首选：官方安装的 Python（推荐，2026-09-20 起本项目 .venv 就构建在它之上）
REM     备用：WorkBuddy 自带的独立解释器（不在 py 启动器注册表里，故需显式探测）
if not defined PYCMD (
    set "OFFICIAL=%LOCALAPPDATA%\Python\pythoncore-3.13-64\python.exe"
    if exist "!OFFICIAL!" (
        "!OFFICIAL!" -c "import sys" >nul 2>&1 && set "PYCMD=!OFFICIAL!"
        if defined PYCMD set "PYDESC=3.13（官方安装，本项目 .venv 的构建基础）"
    )
)
if not defined PYCMD (
    set "BUNDLED=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
    if exist "!BUNDLED!" (
        "!BUNDLED!" -c "import sys" >nul 2>&1 && set "PYCMD=!BUNDLED!"
        if defined PYCMD set "PYDESC=3.13（独立分发解释器，备用路径）"
    )
)

REM (d) 3.12：可装可跑，但未经回归验证
if not defined PYCMD py -3.12 -c "import sys" >nul 2>&1 && set "PYCMD=py -3.12"
if not defined PYDESC if defined PYCMD set "PYDESC=3.12（**未验证路径**，建议改用 3.13；详见 docs\数据复现.md）"

REM (e) 兜底
if not defined PYCMD python -c "import sys" >nul 2>&1 && set "PYCMD=python"
if not defined PYDESC if defined PYCMD set "PYDESC=系统默认 python（版本未确认）"

if not defined PYCMD (
    echo        [错误] 未找到可用的 Python 解释器。
    echo        请安装 Python 3.13（推荐，本项目已验证版本）或 3.12，
    echo        安装时勾选 "Add Python to PATH"；
    echo        也可用环境变量指定，例如：
    echo            set AGRI_PYTHON=C:\path\to\python.exe
    pause
    exit /b 1
)
echo        使用解释器：%PYCMD%
echo        说明：%PYDESC%

REM ---- 2. 创建虚拟环境 ----
echo.
echo [2/5] 创建虚拟环境 .venv ...
if exist ".venv\Scripts\python.exe" (
    echo        已存在，跳过创建。
) else (
    %PYCMD% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
)

set "PY=.venv\Scripts\python.exe"

REM ---- 3. 升级 pip ----
echo.
echo [3/5] 升级 pip ...
"%PY%" -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [警告] pip 升级失败，继续尝试安装依赖。
)

REM ---- 4. 安装 PyTorch（必须早于 ultralytics，否则会被装成 CPU 版）----
echo.
if "%CHOICE%"=="2" (
    echo [4/5] 安装 CPU 版 PyTorch ...
    "%PY%" -m pip install "torch>=2.4" "torchvision" ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    echo        结果：CPU 版。接口联调可用，但推理速度远低于 GPU。
) else (
    echo [4/5] 安装 CUDA 12.6 版 PyTorch ...
    echo        注意：若后续需要换 CUDA 版本，请改下面的 cu 编号，并确认
    echo        驱动版本满足要求，否则 CUDA 不可用。
    REM 关键：阿里云的 pytorch-wheels 是**扁平 wheel 目录**，不是 PEP503 索引。
    REM 因此必须用 -f（--find-links）而不是 --index-url —— 用后者时 pip 会去请求
    REM .../cu126/torch/ 并拿到 HTTP 404，随后静默回落到 PyPI 上**不带 CUDA 版本号**
    REM 的 torch 包，导致"装了 CUDA 版"其实是 CPU 版。
    "%PY%" -m pip install "torch==2.13.0+cu126" "torchvision==0.28.0+cu126" ^
        -f https://mirrors.aliyun.com/pytorch-wheels/cu126/ ^
        -i https://mirrors.aliyun.com/pypi/simple/
    if errorlevel 1 (
        echo.
        echo [错误] CUDA 版 PyTorch 安装失败。
        echo        常见原因：驱动版本过低（CUDA 12.6 需驱动 ^>= 525），或镜像源不可达。
        echo        如本机无 NVIDIA 显卡，请改选 CPU 版（重新运行本脚本并输入 2）。
        pause
        exit /b 1
    )
    REM 断言：确认装到的确实是 CUDA 版。仅凭 pip 成功无法判断 ——
    REM 上面的回落机制会让 CPU 版也"安装成功"，必须在这里显式拦住。
    "%PY%" -c "import sys,torch;sys.exit(0 if torch.cuda.is_available() else 1)"
    if errorlevel 1 (
        echo.
        echo [错误] PyTorch 已安装，但 torch.cuda.is_available^(^) 为 False。
        echo        说明装到的不是可用的 CUDA 版本，或本机驱动不满足要求。
        echo        请执行以下命令查看实际情况：
        echo            .venv\Scripts\python.exe -c "import torch;print^(torch.__version__^)"
        echo        若版本号中不含 "+cu" 后缀，即为回落成了 CPU 版。
        pause
        exit /b 1
    )
)
if errorlevel 1 (
    echo [错误] PyTorch 安装失败。请检查网络与镜像源可用性。
    pause
    exit /b 1
)

REM ---- 5. 安装其余依赖 ----
echo.
echo [5/5] 安装其余依赖（requirements.txt，ultralytics 已锁定版本）...
"%PY%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)

REM ---- 自检 ----
echo.
echo ============================================================
echo   安装完成，正在自检
echo ============================================================
"%PY%" -c "import sys,torch,ultralytics,cv2,fastapi,numpy;print('解释器路径 ',sys.executable);print('Python     ',sys.version.split()[0]);print('torch      ',torch.__version__);print('CUDA 可用  ',torch.cuda.is_available());print('ultralytics',ultralytics.__version__);print('opencv     ',cv2.__version__);print('fastapi    ',fastapi.__version__);print('numpy      ',numpy.__version__)"
if errorlevel 1 (
    echo [警告] 自检未通过，请查看上方报错。
    pause
    exit /b 1
)

echo.
echo 环境就绪。接下来：
echo   1) 确认 models\best.pt 存在（否则系统会用兜底权重，识别结果无实际意义）
echo   2) 运行 run.bat 启动服务
echo   3) 浏览器打开 http://127.0.0.1:8000
echo.
pause
endlocal
