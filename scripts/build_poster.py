"""生成产品海报/封面图（4.8x 超采样 4800x2240 -> 升级为 6x 7200x3360 + 摄影质感）。

设计基准 1200x560（官方建议尺寸同比例），以 K=6 倍原生渲染文字/矢量，
叠加真实病叶摄影卡、高清产品截图卡与 Grad-CAM 热力图卡，营造"高清门面"质感。
JPEG 以 quality=100 + 禁用色度抽样输出，在 8MB 上限内达成最高清晰度。
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MAT = ROOT / "参赛材料"
MEDIA = ROOT / "media"

K = 6                      # 超采样倍数
BASE_W, BASE_H = 1200, 560
W, H = BASE_W * K, BASE_H * K  # 7200 x 3360

FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = "C:/Windows/Fonts/msyh.ttc"

WHITE = (255, 255, 255)
MINT = (188, 240, 208)
CYAN = (34, 211, 238)
GREEN_BRIGHT = (74, 222, 128)


def s(v):
    return round(v * K)


def ft(path, size):
    return ImageFont.truetype(path, s(size))


def bezier(p0, p1, p2, p3, n=48):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def draw_logo(size=128):
    size = s(size)
    scale = size / 128.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ov = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def P(c):
        return [(x * scale, y * scale) for x, y in c]

    upper = bezier((11, 64), (11, 22), (50, 10), (64, 10)) + bezier((64, 10), (78, 10), (117, 22), (117, 64))[1:] + [(64, 64), (11, 64)]
    d.polygon(P(upper), fill=(74, 222, 128))
    lower = bezier((11, 64), (11, 106), (50, 118), (64, 118)) + bezier((64, 118), (78, 118), (117, 106), (117, 64))[1:] + [(64, 64), (11, 64)]
    d.polygon(P(lower), fill=(21, 128, 61))
    d.line(P(bezier((22, 47), (42, 30), (86, 30), (106, 47))), fill=(255, 255, 255, 166), width=max(3, int(3 * scale)), joint="curve")
    d.ellipse(P([(32, 32), (96, 96)]), fill=(103, 232, 249, 56))
    d.ellipse(P([(44, 44), (84, 84)]), fill=(6, 182, 212))
    d.ellipse(P([(53, 53), (75, 75)]), fill=(14, 116, 144))
    d.ellipse(P([(59, 59), (69, 69)]), fill=(255, 255, 255))
    return Image.alpha_composite(img, ov)


def gradient_bg():
    arr = np.zeros((H, W, 3), dtype=np.float32)
    top = np.array([8, 42, 26], dtype=np.float32)
    bot = np.array([16, 72, 44], dtype=np.float32)
    yv = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    arr = top[None, None, :] * (1 - yv) + bot[None, None, :] * yv
    # 右上角额外提亮（径向绿青色光）
    gy, gx = np.ogrid[:H, :W]
    cx, cy = W * 0.82, H * 0.08
    d2 = ((gx - cx) / (W * 0.75)) ** 2 + ((gy - cy) / (H * 0.7)) ** 2
    glow = np.clip(1 - d2, 0, 1)[:, :, None] * 0.5
    arr = arr * (1 - glow * 0.25) + np.array([30, 90, 60], dtype=np.float32)[None, None, :] * (glow * 0.25)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def add_grain(base, amount=3):
    """极轻微胶片颗粒，避免大面积纯色渐变出现色阶断层。"""
    arr = np.asarray(base.convert("RGB"), dtype=np.int16)
    rng = np.random.default_rng(20260830)
    noise = rng.normal(0, amount, (H, W, 3)).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def rounded(im, radius_logical):
    radius = s(radius_logical)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0], im.size[1]), radius, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    out.paste(im, (0, 0), mask)
    return out


def shadowed_card(im, radius, tilt, shadow=90, blur=12):
    """给卡片加投影并轻微旋转。"""
    pad = s(20)
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((s(8), s(12), s(8) + im.width, s(12) + im.height), s(radius), fill=(0, 0, 0, shadow))
    sh = sh.filter(ImageFilter.GaussianBlur(s(blur)))
    canvas = Image.alpha_composite(canvas, sh)
    canvas.paste(im, (s(4), s(4)), im)
    if tilt:
        canvas = canvas.rotate(tilt, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
    return canvas


def center_crop_to(src, aspect):
    """居中裁剪到目标宽高比 aspect=w/h。"""
    w, h = src.size
    ca = w / h
    if ca > aspect:
        nw = int(h * aspect)
        x = (w - nw) // 2
        return src.crop((x, 0, x + nw, h))
    else:
        nh = int(w / aspect)
        y = (h - nh) // 2
        return src.crop((0, y, w, y + nh))


def screenshot_card():
    shot = Image.open(MEDIA / "screens" / "02_result.png").convert("RGB")
    w = s(372)
    h = int(shot.height * w / shot.width)
    shot = shot.resize((w, h), Image.LANCZOS)
    # 上采样后轻微锐化，恢复界面文字与边框的边缘清晰度
    shot = shot.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=2))
    pad = s(13)
    card = Image.new("RGBA", (w + pad * 2, h + pad * 2), WHITE)
    card.paste(shot, (pad, pad))
    return shadowed_card(rounded(card, 16), 16, -2.0)


def photo_card():
    ph = Image.open(MEDIA / "gen" / "leaf_disease_hi.jpg").convert("RGB")
    size = s(220)
    ph = center_crop_to(ph, 1.0).resize((size, size), Image.LANCZOS)
    return shadowed_card(rounded(ph, 16), 16, 2.6)


def heatmap_card():
    hm = Image.open(MAT / "assets" / "heatmap_hi.png").convert("RGB")
    size = s(178)
    hm = center_crop_to(hm, 1.0).resize((size, size), Image.LANCZOS)
    card = rounded(hm, 14)
    # 荧光绿描边
    ring = Image.new("RGBA", card.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.rounded_rectangle((s(3), s(3), card.size[0] - s(3), card.size[1] - s(3)), s(13), outline=(74, 222, 128), width=s(3))
    card = Image.alpha_composite(card, ring)
    return shadowed_card(card, 14, -3.0)


def label(draw, x, y, text, f, tc=(165, 243, 252), bg=(8, 51, 68)):
    tw = draw.textlength(text, font=f)
    draw.rounded_rectangle((x, y, x + tw + s(30), y + s(38)), radius=s(19), fill=bg)
    draw.text((x + s(15), y + s(5)), text, font=f, fill=tc)


def feature_row(draw, y, num, title, desc, accent_color):
    r = s(15)
    cx = s(64) + r
    draw.ellipse((cx - r, y, cx + r, y + 2 * r), fill=accent_color)
    nf = ft(FONT_BOLD, 18)
    draw.text((cx - draw.textlength(num, font=nf) / 2, y + s(4)), num, font=nf, fill=(8, 51, 68))
    tf = ft(FONT_BOLD, 28)
    draw.text((cx + s(32), y - s(2)), title, font=tf, fill=WHITE)
    df = ft(FONT_REG, 20)
    draw.text((cx + s(32), y + s(30)), desc, font=df, fill=MINT)


def build():
    canvas = gradient_bg()
    d = ImageDraw.Draw(canvas)

    # ---- 左上品牌 ----
    logo = draw_logo(88)
    canvas.paste(logo, (s(64), s(48)), logo)
    wf = ft(FONT_BOLD, 54)
    d.text((s(172), s(56)), "禾目 AgriGuard", font=wf, fill=WHITE)
    sf = ft(FONT_REG, 25)
    d.text((s(174), s(126)), "慧眼识农 · 作物健康 AI 医生", font=sf, fill=MINT)

    # ---- 主标题 ----
    hf = ft(FONT_BOLD, 48)
    d.text((s(64), s(196)), "拍一张病叶", font=hf, fill=WHITE)
    d.text((s(64), s(262)), "秒出", font=hf, fill=WHITE)
    tx = s(64) + d.textlength("秒出", font=hf) + s(16)
    d.text((tx, s(262)), "AI 诊断处方", font=hf, fill=GREEN_BRIGHT)

    # ---- 特性 ----
    feature_row(d, s(334), "1", "病害识别", "YOLO 视觉引擎 · 38 类病叶 · 精度 99.8%", CYAN)
    feature_row(d, s(398), "2", "病灶定位", "Grad-CAM 热力图 · 判断可解释", CYAN)
    feature_row(d, s(462), "3", "精准处方", "大模型生成 · 减量增效可落地", CYAN)

    # ---- 左下底部 ----
    bf = ft(FONT_REG, 24)
    d.text((s(64), s(530)), "智慧农业 · 减肥减药 · 数字乡村", font=bf, fill=MINT)

    # ---- 右侧三卡：截图（主）+ 病叶照片 + 热力图 ----
    lf = ft(FONT_BOLD, 18)

    sc = screenshot_card()
    canvas.paste(sc, (s(596), s(118)), sc)

    pc = photo_card()
    canvas.paste(pc, (s(940), s(88)), pc)
    label(d, s(958), s(322), "真实病叶 · 早疫病", lf)

    hc = heatmap_card()
    canvas.paste(hc, (s(600), s(396)), hc)
    label(d, s(782), s(470), "Grad-CAM 病灶定位", lf)

    out = canvas.convert("RGB")
    out.save(MAT / "产品海报.jpg", quality=100, subsampling=0, optimize=True)
    print("saved", MAT / "产品海报.jpg", out.size, out.size.dtype if hasattr(out, 'dtype') else '', sep=" ")


if __name__ == "__main__":
    build()