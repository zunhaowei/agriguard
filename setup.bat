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
set "PYCMD="
py -3.12 -c "import sys" >nul 2>&1 && set "PYCMD=py -3.12"
if not defined PYCMD py -3.13 -c "import sys" >nul 2>&1 && set "PYCMD=py -3.13"
if not defined PYCMD python -c "import sys" >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD (
    echo [错误] 未找到可用的 Python 解释器。
    echo        请安装 Python 3.12 或 3.13，并勾选 "Add Python to PATH"。
    pause
    exit /b 1
)
echo        使用解释器：%PYCMD%

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
) else (
    echo [4/5] 安装 CUDA 12.6 版 PyTorch ...
    echo        注意：若后续需要换 CUDA 版本，请改下面的 cu 编号，并确认
    echo        驱动版本满足要求，否则 torch.cuda.is_available^(^) 会返回 False。
    "%PY%" -m pip install "torch==2.13.0" "torchvision==0.28.0" ^
        --index-url https://mirrors.aliyun.com/pytorch-wheels/cu126/ ^
        --extra-index-url https://mirrors.aliyun.com/pypi/simple/
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
"%PY%" -c "import sys,torch,ultralytics,cv2,fastapi,numpy;print('Python     ',sys.version.split()[0]);print('torch      ',torch.__version__);print('CUDA 可用  ',torch.cuda.is_available());print('ultralytics',ultralytics.__version__);print('opencv     ',cv2.__version__);print('fastapi    ',fastapi.__version__);print('numpy      ',numpy.__version__)"
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
