"""打包「分享版」压缩包：只收交付必需的内容，排除可重建的大体积中间产物。

【为什么要写脚本而不是手动右键压缩】
手动打包每次取舍都不同，容易漏文件（尤其是文档、测试、训练证据），
也容易不小心把 .venv（4.5GB）或 data/（5.5GB 训练集）压进去。
把取舍规则固化成代码，任何人都能得到一致的包。

【包含 / 排除的判定原则】
包含：能证明「我们做了什么」的一切 —— 源码、文档、测试、训练证据、测试素材、成品物料。
排除：体积大且可重建或本机私有的东西 —— 虚拟环境、训练集、上传缓存、版本库、内部协作目录。

用法：
    .venv\\Scripts\\python.exe scripts\\make_share_package.py
    .venv\\Scripts\\python.exe scripts\\make_share_package.py --out D:\\某处\\包.zip
"""

import argparse
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---- 整目录包含（相对路径）----
INCLUDE_DIRS = [
    "backend", "frontend", "scripts", "tests", "docs",
    "models",            # best.pt 3.1MB，不看权重就没法复现
    "runs",              # 训练证据：results.csv / 混淆矩阵 / 训练曲线
    "assets",            # 品牌资源
    "test_assets",       # 50 张分类测试素材
    "参赛材料",           # 海报 + 高清热力图
]

# ---- 单文件包含 ----
INCLUDE_FILES = [
    "README.md", "分享版说明.md", "开发交接文档.md",
    "requirements.txt", "requirements-train.txt", "requirements-materials.txt",
    "run.bat", "setup.bat", "pytest.ini", ".gitignore", ".env.example",
]

# ---- 目录内选择性包含（排除体积大的中间产物）----
INCLUDE_GLOBS = [
    "media/demo_video.mp4",   # 成品视频（中间帧 frames/、audio/ 排除）
    "media/narration.json",
]

# ---- 排除规则（按路径片段匹配）----
EXCLUDE_PARTS = {
    ".venv", "venv", "env",
    "data",                 # 训练集 5.5GB，可用 docs/数据复现.md 重建
    "uploads",              # 运行时上传缓存
    ".git",                 # 版本库（另有远程仓库）
    ".workbuddy",           # 内部协作目录（审查报告/记忆），非交付物
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "media",                # 目录级排除；成品视频由 INCLUDE_GLOBS 单独放行
}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".pdb", ".zip"}
EXCLUDE_NAME_PARTS = {"_preview", "frames", "audio", "narr_full", "_probe",
                     "weights"}  # runs/**/weights/ 与 models/best.pt 是同一份，去重

# 显式放行：这些路径虽然落在被排除的目录下（如 media/），但属于交付成品
ALLOW_EXACT = {
    "media/demo_video.mp4",
    "media/narration.json",
}


def should_skip(rel: Path) -> bool:
    posix = str(rel).replace("\\", "/")
    if posix in ALLOW_EXACT:
        return False  # 显式放行优先于目录级排除
    parts = set(rel.parts)
    if parts & EXCLUDE_PARTS:
        return True
    if rel.suffix.lower() in EXCLUDE_SUFFIX:
        return True
    if any(seg in posix for seg in EXCLUDE_NAME_PARTS):
        return True
    return False


def collect() -> list:
    files = []
    for d in INCLUDE_DIRS:
        base = ROOT / d
        if not base.exists():
            print(f"  [警告] 目录不存在，跳过：{d}")
            continue
        for p in base.rglob("*"):
            if p.is_file():
                rel = p.relative_to(ROOT)
                if not should_skip(rel):
                    files.append(p)
    for f in INCLUDE_FILES:
        p = ROOT / f
        if p.exists():
            files.append(p)
        else:
            print(f"  [警告] 文件不存在，跳过：{f}")
    for g in INCLUDE_GLOBS:
        for p in ROOT.glob(g):
            if p.is_file() and not should_skip(p.relative_to(ROOT)):
                files.append(p)
    # 去重并稳定排序
    return sorted(set(files), key=lambda x: str(x.relative_to(ROOT)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="输出 zip 路径；默认放在工作区根目录")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d")
    out = Path(args.out) if args.out else (ROOT.parent / f"禾目AgriGuard_分享版_{stamp}.zip")
    out.parent.mkdir(parents=True, exist_ok=True)

    files = collect()
    print(f"待打包文件：{len(files)} 个")

    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            arc = p.relative_to(ROOT)
            z.write(p, arcname=str(Path("禾目AgriGuard") / arc))
            total += p.stat().st_size

    size = out.stat().st_size
    print(f"原始体积：{total/1024/1024:.1f} MB")
    print(f"压缩后  ：{size/1024/1024:.1f} MB")
    print(f"输出    ：{out}")

    # 打印体积最大的若干文件，便于确认没误收大东西
    print("\n包内最大的 12 个文件：")
    top = sorted(files, key=lambda x: -x.stat().st_size)[:12]
    for p in top:
        print(f"  {p.stat().st_size/1024/1024:7.2f} MB  {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
