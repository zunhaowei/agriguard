@echo off
chcp 65001 >nul
setlocal
title 禾目 AgriGuard - 作物病虫害智能诊断服务
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
REM 缺失时服务仍能启动（回落到 models\yolo11n-cls.pt 兜底权重），
REM 但兜底权重的识别结果**没有任何实际意义**。赛前若发生这种情况，
REM 必须明确拦住而不是"警告后照常启动" —— 否则极可能拿错结果去演示。
if not exist "models\best.pt" (
    echo [警告] 未找到生产权重：models\best.pt
    echo.
    if not exist "models\yolo11n-cls.pt" (
        echo [错误] 兜底权重 models\yolo11n-cls.pt 也不存在，服务无法启动。
        echo        请先放置模型权重。
        pause
        exit /b 1
    )
    echo        服务将回落到通用预训练兜底权重启动，
    echo        **识别结果无实际意义，不可用于演示或评审**。
    echo.
    echo        若只是做接口联调，可继续；若准备演示，请先补齐 best.pt。
    echo.
    set "GO="
    set /p GO=确认继续？输入 y 回车，其它任意键退出： 
    if /i not "%GO%"=="y" (
        echo 已取消启动。
        pause
        exit /b 1
    )
    echo.
)

REM ---- 前置检查 3：端口占用 ----
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [错误] 端口 8000 已被占用，服务无法启动。
    echo        查看占用进程：netstat -ano ^| findstr :8000
    echo        停止该进程：  taskkill /PID ^<进程号^> /F
    pause
    exit /b 1
)

REM 不写字节码：避免在只读目录或受限环境下产生 .pyc 写入报错
set PYTHONDONTWRITEBYTECODE=1
REM 离线优先：模型一律从本地加载，不做联网下载与遥测（现场网络不可控）。
REM 注意：ultralytics 8.4.137 中真正生效的只有 YOLO_OFFLINE 这一个变量；
REM 曾设置的 ULTRALYTICS_OFFLINE 在该版本零引用、完全无效，故不再设置。
set YOLO_OFFLINE=true

cd backend

echo 启动中…… 首次启动会在无人操作时预加载模型并预热推理（约 5-9 秒），
echo 之后每次识别都在百毫秒级。请等出现 "Application startup complete" 再打开页面。
echo.
echo 访问地址：http://127.0.0.1:8000
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
