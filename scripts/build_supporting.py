"""打包「其他证明材料」zip：训练数据/指标 + 运行截图 + 核心代码 + 模型权重 + 项目文档。

重绘高清训练曲线（含 Top-1/Top-5 精度与 loss），用高 DPI 输出保证清晰度。
注意：不打包 .env / 任何含 API Key 的文件。
"""
import csv
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAT = ROOT / "参赛材料"
RUNS = ROOT / "runs" / "agriguard"
STAGE = ROOT / "_supporting_stage"
OUT = MAT / "其他证明材料.zip"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

GREEN = "#2E7D4F"
GREEN_DARK = "#1F5E3A"
GREEN_LIGHT = "#B9E6C9"
MUTED = "#64748B"


def _read_csv():
    rows = {}
    with open(RUNS / "results.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r = {k.strip(): v.strip() for k, v in r.items() if k and v}
            for k, v in r.items():
                rows.setdefault(k, []).append(float(v))
    return rows


def redraw_curve():
    """从 results.csv 重绘高清训练曲线，输出 2600x1500 PNG。"""
    data = _read_csv()
    epoch = data["epoch"]
    top1 = [v * 100 for v in data["metrics/accuracy_top1"]]
    top5 = [v * 100 for v in data["metrics/accuracy_top5"]]
    val_loss = data["val/loss"]
    train_loss = data["train/loss"]

    fig, ax = plt.subplots(figsize=(13, 7.5), dpi=200)
    ax2 = ax.twinx()

    l1, = ax.plot(epoch, top1, color=GREEN,
                  linewidth=2.4, label="Top-1 准确率", marker="o", markersize=3)
    l2, = ax.plot(epoch, top5, color=GREEN_LIGHT,
                  linewidth=2.0, label="Top-5 准确率", marker="s", markersize=2.6)
    l3, = ax2.plot(epoch, val_loss, color="#E58E26", linewidth=2.2,
                   label="验证损失 val/loss", linestyle="--")
    l4, = ax2.plot(epoch, train_loss, color="#C0392B", linewidth=2.0,
                   label="训练损失 train/loss", linestyle=":")

    ax.set_xlabel("轮次 Epoch", fontsize=13)
    ax.set_ylabel("准确率 Accuracy (%)", fontsize=13, color=GREEN_DARK)
    ax2.set_ylabel("损失 Loss", fontsize=13, color=MUTED)
    ax.set_title("禾目 AgriGuard · YOLO11n 病害识别模型训练曲线（30 epochs）",
                 fontsize=15, fontweight="bold", color=GREEN_DARK, pad=14)

    ax.set_ylim(85, 101)
    ax.set_xlim(1, 30)
    ax.grid(True, which="both", axis="y", alpha=0.25, linewidth=0.6)
    ax.tick_params(axis="y", labelcolor=GREEN_DARK)
    ax2.tick_params(axis="y", labelcolor=MUTED)

    lines = [l1, l2, l3, l4]
    ax.legend(lines, [l.get_label() for l in lines], loc="lower right",
              frameon=True, framealpha=0.95, fontsize=11)
    fig.tight_layout()
    out_path = STAGE / "01_训练数据与指标" / "training_curve.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("curve done")


def build():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "01_训练数据与指标").mkdir(parents=True)
    (STAGE / "02_系统运行截图").mkdir(parents=True)
    (STAGE / "03_核心代码").mkdir(parents=True)
    (STAGE / "04_模型与权重").mkdir(parents=True)
    (STAGE / "05_项目文档").mkdir(parents=True)

    redraw_curve()

    # 01 训练数据与指标
    d1 = STAGE / "01_训练数据与指标"
    for f in ["results.csv", "args.yaml", "confusion_matrix.png",
              "confusion_matrix_normalized.png", "results.png",
              "val_batch0_pred.jpg", "val_batch0_labels.jpg",
              "val_batch1_pred.jpg", "val_batch2_pred.jpg"]:
        src = RUNS / f
        if src.exists():
            shutil.copy2(src, d1 / f)
    # 训练批次样张（前几张，展示数据增强）
    for f in ["train_batch0.jpg", "train_batch1.jpg", "train_batch2.jpg"]:
        src = RUNS / f
        if src.exists():
            shutil.copy2(src, d1 / f)

    # 02 系统运行截图
    d2 = STAGE / "02_系统运行截图"
    screens = {
        "01_home.png": "系统首页.png",
        "02_result.png": "诊断结果.png",
        "04_bottom_prescription.png": "精准处方.png",
    }
    for src_name, dst_name in screens.items():
        src = ROOT / "media" / "screens" / src_name
        if src.exists():
            shutil.copy2(src, d2 / dst_name)

    # 03 核心代码
    d3 = STAGE / "03_核心代码"
    for f in ["config.py", "detector.py", "gradcam.py", "main.py",
              "prescriber.py", "schemas.py"]:
        src = ROOT / "backend" / "app" / f
        if src.exists():
            shutil.copy2(src, d3 / f)
    for f in ["train.py", "organize_data.py", "download_dataset.py",
              "finalize_train.py", "smoke_test.py", "test_gradcam.py"]:
        src = ROOT / "scripts" / f
        if src.exists():
            shutil.copy2(src, d3 / f)

    # 04 模型与权重
    d4 = STAGE / "04_模型与权重"
    for f in ["best.pt", "yolo11n-cls.pt"]:
        src = ROOT / "models" / f
        if src.exists():
            shutil.copy2(src, d4 / f)

    # 05 项目文档
    d5 = STAGE / "05_项目文档"
    for f in ["README.md", "开发交接文档.md"]:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, d5 / f)

    # 打包
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(STAGE))
    size = OUT.stat().st_size
    print(f"打包完成: {OUT}  ({size/1024/1024:.2f} MB)")


if __name__ == "__main__":
    build()