"""生成 PPT 所需素材：透明 LOGO + 训练精度曲线。"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
ASSET = ROOT / "参赛材料" / "assets"
MEDIA = ROOT / "media"
ASSET.mkdir(parents=True, exist_ok=True)

PRIMARY = "#1F5E3A"
SECONDARY = "#2E7D4F"
MINT = "#86EFAC"
CYAN = "#0E7490"
GOLD = "#C49A42"


def draw_logo(size=512):
    s = size / 128.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ov = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def P(c):
        return [(x * s, y * s) for x, y in c]

    def bezier(p0, p1, p2, p3, n=32):
        pts = []
        for i in range(n + 1):
            t = i / n
            mt = 1 - t
            x = mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0]
            y = mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1]
            pts.append((x, y))
        return pts

    upper = bezier((11, 64), (11, 22), (50, 10), (64, 10)) + bezier((64, 10), (78, 10), (117, 22), (117, 64))[1:] + [(64, 64), (11, 64)]
    lower = bezier((11, 64), (11, 106), (50, 118), (64, 118)) + bezier((64, 118), (78, 118), (117, 106), (117, 64))[1:] + [(64, 64), (11, 64)]
    d.polygon(P(upper), fill=(74, 222, 128))
    d.polygon(P(lower), fill=(21, 128, 61))
    d.line(P(bezier((22, 47), (42, 30), (86, 30), (106, 47))), fill=(255, 255, 255, 166), width=max(3, int(3 * s)), joint="curve")
    d.ellipse(P([(32, 32), (96, 96)]), fill=(103, 232, 249, 56))
    d.ellipse(P([(44, 44), (84, 84)]), fill=(6, 182, 212))
    d.ellipse(P([(53, 53), (75, 75)]), fill=(14, 116, 144))
    d.ellipse(P([(59, 59), (69, 69)]), fill=(255, 255, 255))
    Image.alpha_composite(img, ov).save(ASSET / "logo_512x512.png")
    print("logo done")


def acc_curve():
    epochs = list(range(1, 31))
    top1 = [0.9658, 0.96617, 0.91242, 0.9734, 0.97572, 0.98165, 0.98795, 0.98703, 0.98999, 0.99305,
            0.9937, 0.99481, 0.99425, 0.99546, 0.99555, 0.99583, 0.99629, 0.9962, 0.99657, 0.99657,
            0.99731, 0.9974, 0.99731, 0.9974, 0.99759, 0.99768, 0.99787, 0.99796, 0.99796, 0.99796]
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=320)
    ax.plot(epochs, top1, color=PRIMARY, linewidth=2.8, marker="o", markersize=3.5)
    ax.fill_between(epochs, top1, min(top1) - 0.005, color=SECONDARY, alpha=0.12)
    ax.scatter([30], [0.99796], color=GOLD, s=90, zorder=5)
    ax.annotate("99.8% (Top-1)", xy=(30, 0.99796), xytext=(20, 0.973),
                fontsize=12, color=PRIMARY, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=GOLD, lw=1.6))
    ax.set_xlabel("训练轮次 (epoch)", fontsize=11, color="#334155")
    ax.set_ylabel("Top-1 准确率", fontsize=11, color="#334155")
    ax.set_ylim(0.90, 1.005)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout(pad=0.4)
    fig.savefig(ASSET / "top1_curve.png", transparent=True)
    plt.close(fig)
    print("curve done", Image.open(ASSET / "top1_curve.png").size)


def heatmap_hi(size=1280):
    """将 256x256 的 Grad-CAM 热力图放大为高清素材（热力图为平滑色块，放大无锯齿）。"""
    hm = Image.open(MEDIA / "heatmap.jpg").convert("RGB")
    hm = hm.resize((size, size), Image.LANCZOS)
    hm.save(ASSET / "heatmap_hi.png")
    print("heatmap done", hm.size)


if __name__ == "__main__":
    draw_logo()
    acc_curve()
    heatmap_hi()
    print("assets in", ASSET)