@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] 未找到虚拟环境，请先运行 setup.bat
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
cd backend
echo 启动服务，浏览器访问 http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000