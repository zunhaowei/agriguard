@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/4] 创建虚拟环境 (.venv) ...
py -3.12 -m venv .venv
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] 未找到 Python 3.12，请先安装 Python 3.12。
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

echo [2/4] 升级 pip（清华镜像）...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [3/4] 安装 PyTorch ...
echo   尝试 CUDA 12.1 版（阿里云镜像，约 2.5GB）...
python -m pip install "torch==2.5.1+cu121" "torchvision==0.20.1+cu121" -f https://mirrors.aliyun.com/pytorch-wheels/cu121/ -i https://mirrors.aliyun.com/pypi/simple/
if errorlevel 1 (
    echo   CUDA 版下载失败，回退安装 CPU 版 PyTorch（清华镜像，约 200MB）...
    python -m pip install torch torchvision -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [ERROR] PyTorch 安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)

echo [4/4] 安装其余依赖（清华镜像）...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [ERROR] 其余依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
)

echo.
echo 全部安装完成！运行 run.bat 启动服务。
pause