@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   禾目 AgriGuard - 作物病虫害智能诊断与精准处方系统
echo ============================================================
echo.

set "PY=.venv\Scripts\python.exe"
REM 记录绝对路径：后面会 cd 到 backend，相对路径会失效
set "VENVPY=%~dp0.venv\Scripts\python.exe"

REM ---- 前置检查 1：虚拟环境 ----
if not exist "%PY%" (
    echo [错误] 未找到虚拟环境：%PY%
    echo        请先双击运行 setup.bat 完成环境安装。
    pause
    exit /b 1
)

REM ---- 前置检查 2：模型权重 ----
REM 说明：缺失时服务仍能启动（会回落到 models\yolo11n-cls.pt 兜底权重），
REM 但兜底权重识别结果无实际意义，因此这里必须显式提醒，避免拿错结果去演示。
if not exist "models\best.pt" (
    echo [警告] 未找到生产权重 models\best.pt
    if exist "models\yolo11n-cls.pt" (
        echo        服务将以通用预训练兜底权重启动，**识别结果无实际意义**，
        echo        请勿用于演示或评审。
    ) else (
        echo        且兜底权重 models\yolo11n-cls.pt 也不存在，服务将无法启动。
        pause
        exit /b 1
    )
    echo.
)

REM ---- 前置检查 3：端口占用 ----
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [错误] 端口 8000 已被占用，服务无法启动。
    echo        可执行以下命令查看占用进程：
    echo            netstat -ano ^| findstr :8000
    pause
    exit /b 1
)

REM 不写字节码：避免在只读目录或受限环境下产生 .pyc 写入报错
set PYTHONDONTWRITEBYTECODE=1
REM 离线优先：模型一律从本地加载，不做联网下载与遥测（现场网络不可控）
set YOLO_OFFLINE=true
set ULTRALYTICS_OFFLINE=true

cd backend

echo 启动中…… 首次启动会预加载模型（约 5-8 秒），请稍候。
echo 启动完成后浏览器访问：http://127.0.0.1:8000
echo 停止服务：在本窗口按 Ctrl+C
echo.

"%VENVPY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 (
    echo.
    echo [错误] 服务异常退出，请查看上方报错信息。
    pause
    exit /b 1
)

endlocal
