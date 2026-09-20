"""禾目 AgriGuard 演示视频 v2：真实操作流程动态演示 + 中文语音旁白。

渲染动态帧（无音轨）-> 拼接旁白音轨 -> 完整 ffmpeg 合成 H.264+AAC 的 MP4。
"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
AUDIO = MEDIA / "audio"
FFMPEG = str(Path(imageio_ffmpeg.get_ffmpeg_exe()))

W, H = 1920, 1080
FPS = 30
PRE, POST = 0.35, 0.65  # 每场景前/后缓冲秒

# ---- 配色（与前端 styles.css 一致）----
GREEN = (46, 125, 79)
GREEN_DARK = (31, 94, 58)
GREEN_LIGHT = (234, 245, 238)
GREEN_BG_TOP = (246, 251, 248)
GREEN_BG_BOT = (237, 245, 239)
INK = (31, 41, 51)
MUTED = (100, 116, 139)
LINE = (226, 232, 240)
WHITE = (255, 255, 255)
DANGER = (192, 57, 43)
BAR_BG = (240, 242, 245)
BAR_LINE = (222, 226, 232)

FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = "C:/Windows/Fonts/msyh.ttc"

# ---- 浏览器外壳 ----
BAR_H = 64
CONTENT_Y0 = BAR_H

# ---- 真实素材（高清源）----
LEAF_SRC = MEDIA / "gen" / "leaf_disease_hi.jpg"
HEAT_SRC = ASSET_HT = ROOT / "参赛材料" / "assets" / "heatmap_hi.png"
LEAF = Image.open(LEAF_SRC).convert("RGB")
HEAT = Image.open(HEAT_SRC).convert("RGB")


def ft(path, size):
    return ImageFont.truetype(path, size)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a, b):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t, 0, 1)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t, 0, 1)
    return t * t * (3 - 2 * t)


def _vgrad(top, bot):
    arr = np.empty((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / (H - 1)
        arr[y, :, :] = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    return Image.fromarray(arr, "RGB")


# ================= 缓存静态图形 =================
_cache = {}


def browser_shell():
    if "shell" in _cache:
        return _cache["shell"]
    img = Image.new("RGB", (W, H), GREEN_BG_TOP)
    d = ImageDraw.Draw(img)
    # 地址栏
    d.rectangle((0, 0, W, BAR_H), fill=BAR_BG)
    d.line((0, BAR_H - 1, W, BAR_H - 1), fill=BAR_LINE, width=2)
    # 三个圆点
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((28 + i * 34, 22, 28 + i * 34 + 18, 22 + 18), fill=c)
    # 地址栏白条
    d.rounded_rectangle((W // 2 - 300, 14, W // 2 + 300, 50), radius=18, fill=WHITE, outline=BAR_LINE)
    url = "http://127.0.0.1:8000"
    uf = ft(FONT_REG, 24)
    uw = d.textlength(url, font=uf)
    d.text(((W - uw) / 2, 22), url, font=uf, fill=MUTED)
    # 绿底渐变内容区
    grad = Image.new("RGB", (1, H - BAR_H))
    gp = grad.load()
    for y in range(H - BAR_H):
        t = y / (H - BAR_H - 1)
        gp[0, y] = tuple(int(GREEN_BG_TOP[i] + (GREEN_BG_BOT[i] - GREEN_BG_TOP[i]) * t) for i in range(3))
    img.paste(grad.resize((W, H - BAR_H)), (0, BAR_H))
    # 底部 footer
    ff = ft(FONT_REG, 26)
    ftxt = "智慧农业 · 减肥减药 · 数字乡村"
    fw = d.textlength(ftxt, font=ff)
    d.text(((W - fw) / 2, H - 70), ftxt, font=ff, fill=(148, 163, 184))
    _cache["shell"] = img
    return img


def hero():
    if "hero" in _cache:
        return _cache["hero"]
    img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = W // 2
    # 标题
    t1 = ft(FONT_BOLD, 84)
    t2 = ft(FONT_REG, 80)
    a = "禾目 "
    b = "AgriGuard"
    wa, wb = d.textlength(a, font=t1), d.textlength(b, font=t2)
    total = wa + wb
    x = cx - total / 2
    d.text((x, 96), a, font=t1, fill=INK)
    d.text((x + wa, 100), b, font=t2, fill=GREEN)
    sf = ft(FONT_REG, 34)
    stxt = "拍一张病叶照片，秒出诊断与防治处方"
    sw = d.textlength(stxt, font=sf)
    d.text((cx - sw / 2, 208), stxt, font=sf, fill=MUTED)
    _cache["hero"] = img
    return img


def _ai_badge(dark=False):
    key = ("aibadge", dark)
    if key in _cache:
        return _cache[key]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    txt = "AI 辅助制作"
    fnt = ft(FONT_BOLD, 32)
    tw = d.textlength(txt, font=fnt)
    pad = 48
    bh = 52
    bx0 = W - pad - tw - 56
    bx1 = W - pad
    by0 = H - 140
    by1 = by0 + bh
    if dark:
        d.rounded_rectangle((bx0, by0, bx1, by1), radius=bh // 2, outline=(191, 224, 204), width=2)
        d.text((bx0 + 28, by0 + 11), txt, font=fnt, fill=(220, 240, 228))
    else:
        d.rounded_rectangle((bx0, by0, bx1, by1), radius=bh // 2, fill=(255, 255, 255, 235), outline=(191, 224, 204), width=2)
        d.text((bx0 + 28, by0 + 11), txt, font=fnt, fill=GREEN_DARK)
    _cache[key] = lay
    return lay


def card(box, fill=WHITE, outline=LINE):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=20, fill=fill, outline=outline, width=2)
    return img


def dashed_rect(d, box, color, dash=18, gap=12, width=3):
    import math
    x0, y0, x1, y1 = box
    pts = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for p0, p1 in pts:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy)
        n = max(1, int(length / (dash + gap)))
        for i in range(n):
            s = i * (dash + gap) / length
            e = min(1.0, (i * (dash + gap) + dash) / length)
            d.line((p0[0] + dx * s, p0[1] + dy * s, p0[0] + dx * e, p0[1] + dy * e), fill=color, width=width)


def load_image(path, height=None, width=None):
    img = Image.open(path).convert("RGB")
    if height:
        r = height / img.height
        img = img.resize((int(img.width * r), height), Image.LANCZOS)
    elif width:
        r = width / img.width
        img = img.resize((width, int(img.height * r)), Image.LANCZOS)
    return img


def bgr(frame_rgb):
    return np.asarray(frame_rgb)[:, :, ::-1].copy()


# ================= 鼠标光标 =================
def draw_cursor(canvas, x, y, press=False):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    s = 30
    pts = [(x, y), (x, y + 5 * s * 0.7), (x + int(s * 0.5), y + int(s * 0.42)),
           (x + int(s * 0.18), y + int(s * 0.18))]
    # 黑色描边
    d.polygon([(p[0], p[1]) for p in pts] + [(x + 2, y)], fill=(255, 255, 255, 255))
    d.line(pts, fill=(25, 25, 25, 255), width=3)
    # 涟漪
    if press:
        d.ellipse((x - 20, y - 20, x + 20, y + 20), outline=(46, 125, 79, 255), width=4)
        d.ellipse((x - 12, y - 12, x + 12, y + 12), outline=(46, 125, 79, 180), width=3)
    canvas.alpha_composite(layer)
    return canvas


# ================= 场景渲染 =================

def s01_title(t, dur):
    # 深绿渐变全屏品牌卡
    top, bot = (17, 66, 40), (34, 110, 66)
    img = _vgrad(top, bot)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = ease_out(t / (dur * 0.45))
    cx = W // 2
    t1 = ft(FONT_BOLD, 150)
    t2 = ft(FONT_REG, 110)
    a1, b1 = "禾目 ", "AgriGuard"
    wa, wb = d.textlength(a1, font=t1), d.textlength(b1, font=t2)
    x = cx - (wa + wb) / 2
    d.text((x, 300), a1, font=t1, fill=WHITE)
    d.text((x + wa, 344), b1, font=t2, fill=(178, 224, 194))
    sf = ft(FONT_BOLD, 54)
    stxt = "作物病虫害智能诊断与精准处方系统"
    sw = d.textlength(stxt, font=sf)
    d.text((cx - sw / 2, 545), stxt, font=sf, fill=(232, 244, 237))
    tf = ft(FONT_REG, 40)
    tag = "智慧农业 · 减肥减药 · 数字乡村"
    tw = d.textlength(tag, font=tf)
    d.text((cx - tw / 2, 650), tag, font=tf, fill=(200, 224, 210))
    layer.putalpha(layer.split()[3].point(lambda p: int(p * a)))
    layer.alpha_composite(_alpha_layer(_ai_badge(dark=True), a))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _alpha_layer(layer, a):
    layer = layer.copy()
    layer.putalpha(layer.split()[3].point(lambda p: int(p * a)))
    return layer


def s02_pain(t, dur):
    img = Image.new("RGB", (W, H), WHITE)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = W // 2
    a0 = ease_out(t / 0.6)
    d.rounded_rectangle((cx - 150, 130, cx + 150, 130 + 72), radius=36, fill=GREEN_LIGHT)
    d.text((cx - 105, 148), "行业痛点", font=ft(FONT_BOLD, 42), fill=GREEN_DARK)
    title = "作物生病，最怕看错病、用错药"
    tf_ = ft(FONT_BOLD, 72)
    tw = d.textlength(title, font=tf_)
    d.text((cx - tw / 2, 300), title, font=tf_, fill=INK)
    items = [
        ("传统诊断依赖专家经验，基层缺技术", 480 + 0),
        ("农户看病难、开方难，凭感觉盲目用药", 480 + 140),
        ("防治效果差，农药残留高，成本增加", 480 + 280),
    ]
    for i, (txt, y) in enumerate(items):
        a = ease_out((t - 0.5 - i * 0.6) / 0.6)
        if a <= 0:
            continue
        lay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay2)
        dd.ellipse((140, y + 18, 140 + 18, y + 36), fill=GREEN)
        fnt = ft(FONT_REG, 50)
        dd.text((200, y), txt, font=fnt, fill=INK)
        layer.alpha_composite(_alpha_layer(lay2, a))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _upload_card_frame(highlight=0.0):
    box = (480, 380, 480 + 960, 380 + 380)
    lay = card(box)
    d = ImageDraw.Draw(lay)
    # 虚线边框（四边，hover 时变绿加粗）
    if highlight > 0.05:
        color = GREEN
        width = 5
    else:
        color = (135, 165, 145)
        width = 3
    dashed_rect(d, box, color, dash=20, gap=12, width=width)
    hx = box[0] + (box[2] - box[0]) // 2
    hy = box[1] + (box[3] - box[1]) // 2
    if highlight > 0.05:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(box, radius=20, fill=(234, 245, 238, 160))
        lay.alpha_composite(overlay)
        d = ImageDraw.Draw(lay)
    d.text((hx - 20, hy - 90), "+", font=ft(FONT_REG, 90), fill=GREEN)
    f1 = ft(FONT_REG, 40)
    t1 = "点击或拖拽上传病叶照片"
    w1 = d.textlength(t1, font=f1)
    d.text((hx - w1 / 2, hy - 10), t1, font=f1, fill=MUTED)
    f2 = ft(FONT_REG, 26)
    t2 = "支持 jpg / png，建议拍摄清晰的单株病叶"
    w2 = d.textlength(t2, font=f2)
    d.text((hx - w2 / 2, hy + 70), t2, font=f2, fill=(148, 163, 184))
    return lay


def s03_upload(t, dur):
    img = browser_shell().convert("RGBA")
    img.alpha_composite(hero())
    img.alpha_composite(_ai_badge())
    # 上传框
    hl = 0.0
    if 2.4 <= t <= 3.2:
        hl = ease_out((t - 2.4) / 0.6)
    elif t > 3.2:
        hl = 1.0
    img.alpha_composite(_upload_card_frame(hl))
    # 鼠标
    if t < 1.2:
        mx, my = W - 120, H - 120
    elif t < 2.6:
        k = ease_in_out((t - 1.2) / 1.4)
        mx, my = lerp(W - 120, 960, k), lerp(H - 120, 560, k)
    else:
        mx, my = 960, 560
    press = 3.0 <= t <= 3.5
    # 点击后 → 预览图淡入
    if t >= 3.5:
        a = ease_out((t - 3.5) / 0.6)
        prev = load_image(LEAF_SRC, height=230)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(lay)
        px0 = W // 2 - prev.width // 2
        lay.paste(prev, (px0, 772))
        sf2 = ft(FONT_BOLD, 30)
        d2.text((px0 + prev.width + 28, 872), "已上传", font=sf2, fill=GREEN_DARK)
        img.alpha_composite(_alpha_layer(lay, a))
    draw_cursor(img, mx, my, press)
    return img.convert("RGB")


def _leaf_preview():
    return load_image(LEAF_SRC, height=300)


def s04_detect(t, dur):
    img = browser_shell().convert("RGBA")
    # 顶部小标题
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx = W // 2
    d.text((cx - 180, 120), "进行病害诊断", font=ft(FONT_BOLD, 52), fill=INK)
    img.alpha_composite(lay)
    # 病叶预览（始终展示，居中偏左）
    prev = _leaf_preview()
    img.paste(prev, (W // 2 - 420 - prev.width // 2, 380))
    # 右侧结果区
    rx = W // 2 + 80
    card_box = (rx - 60, 380, W - 120, 660)
    ccx = (card_box[0] + card_box[2]) // 2
    if t < 2.8:
        # loading 转圈
        ang = (t * 360) % 360
        lay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay2)
        ccy = 500
        dd.arc((ccx - 40, ccy - 40, ccx + 40, ccy + 40), ang, ang + 270, fill=GREEN, width=8)
        f = ft(FONT_REG, 40)
        txt = "正在诊断中..."
        dd.text((ccx - dd.textlength(txt, font=f) / 2, ccy + 60), txt, font=f, fill=MUTED)
        img.alpha_composite(lay2)
    else:
        a = ease_out((t - 2.8) / 0.5)
        lay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay2)
        # 结果卡
        dd.rounded_rectangle(card_box, radius=20, fill=WHITE, outline=LINE, width=2)
        dd.text((rx - 20, 420), "诊断结果", font=ft(FONT_BOLD, 44), fill=MUTED)
        name = "番茄 · 早疫病"
        nf = ft(FONT_BOLD, 72)
        dd.text((rx - 20, 490), name, font=nf, fill=GREEN_DARK)
        # 置信度徽章
        cf = ft(FONT_BOLD, 42)
        ctxt = "置信度 100.0%"
        cw = dd.textlength(ctxt, font=cf)
        dd.rounded_rectangle((rx - 20, 585, rx - 20 + cw + 46, 585 + 62), radius=31,
                             fill=GREEN_LIGHT, outline=(191, 224, 204), width=2)
        dd.text((rx + 3, 595), ctxt, font=cf, fill=GREEN_DARK)
        # 滑入位移
        img.alpha_composite(_alpha_layer(lay2, a))
    return img.convert("RGB")


def s05_heatmap(t, dur):
    img = browser_shell().convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx = W // 2
    ttl = "病灶定位 · Grad-CAM 类激活图"
    tf_ = ft(FONT_BOLD, 52)
    tw = d.textlength(ttl, font=tf_)
    d.text((cx - tw / 2, 100), ttl, font=tf_, fill=INK)
    img.alpha_composite(lay)
    # 原图与热力图（同尺寸），居中
    disp_h = 720
    orig = load_image(LEAF_SRC, height=disp_h)
    heat = load_image(HEAT_SRC, height=disp_h)
    # 并排
    gap = 60
    total_w = orig.width * 2 + gap
    x0 = (W - total_w) // 2
    y0 = 220
    # 主体：原图在左，热力图在右，右侧淡入
    img.paste(orig, (x0, y0))
    a = ease_out((t - 1.2) / 1.4)
    lay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay2.paste(heat, (x0 + orig.width + gap, y0))
    img.alpha_composite(_alpha_layer(lay2, a))
    # 标签
    lay3 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(lay3)
    lf = ft(FONT_BOLD, 44)
    for xx, txt, col in [(x0, "原图", MUTED), (x0 + orig.width + gap, "病灶热力图", GREEN_DARK)]:
        ww = d3.textlength(txt, font=lf)
        d3.text((xx + (orig.width - ww) / 2, y0 + disp_h + 20), txt, font=lf, fill=col)
    img.alpha_composite(lay3)
    return img.convert("RGB")


def s06_prescription(t, dur):
    img = browser_shell().convert("RGBA")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx = W // 2
    ttl = "精准防治处方"
    tf_ = ft(FONT_BOLD, 52)
    tw = d.textlength(ttl, font=tf_)
    d.text((cx - tw / 2, 90), ttl, font=tf_, fill=INK)
    img.alpha_composite(lay)
    # 三个板块依次滑入
    blocks = [
        ("化学用药", GREEN, "68% 精甲霜·锰锌 600 倍液；或 50% 异菌脲 1000 倍液，安全间隔期 3–7 天"),
        ("生物防治", GREEN, "枯草芽孢杆菌 500 倍液，5–7 天一次，连喷 2 次"),
        ("日常管理", GREEN, "摘除病叶老叶集中处理，改漫灌为滴灌，及时通风排湿，整枝打杈保证透光"),
    ]
    start_y = 220
    bh = 190
    for i, (tag, col, txt) in enumerate(blocks):
        a = ease_out((t - 0.8 - i * 1.6) / 0.6)
        if a <= 0:
            continue
        off = int((1 - a) * 50)
        y = start_y + i * (bh + 30) + off
        lay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay2)
        dd.rounded_rectangle((cx - 560, y, cx + 560, y + bh), radius=18, fill=WHITE, outline=LINE, width=2)
        dd.rounded_rectangle((cx - 540, y + 24, cx - 540 + 190, y + 24 + 52), radius=26, fill=GREEN_LIGHT)
        lf = ft(FONT_BOLD, 36)
        tw_ = dd.textlength(tag, font=lf)
        dd.text((cx - 540 + (190 - tw_) / 2, y + 32), tag, font=lf, fill=GREEN_DARK)
        # 正文，自动换行
        bf = ft(FONT_REG, 38)
        maxw = 860
        lines, cur = [], ""
        for ch in txt:
            if dd.textlength(cur + ch, font=bf) <= maxw:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        ty = y + 30
        for ln in lines:
            dd.text((cx - 320, ty), ln, font=bf, fill=INK)
            ty += bf.size + 12
        img.alpha_composite(_alpha_layer(lay2, a))
    return img.convert("RGB")


def s07_value(t, dur):
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx = W // 2
    ttl = "完整防治闭环"
    tf_ = ft(FONT_BOLD, 56)
    tw = d.textlength(ttl, font=tf_)
    d.text((cx - tw / 2, 110), ttl, font=tf_, fill=GREEN_DARK)
    img.alpha_composite(lay)
    steps = ["识别", "定位", "评估", "处方"]
    sw = 300
    total = sw * 4 + 90 * 3
    x0 = (W - total) // 2
    y = 340
    for i, name in enumerate(steps):
        sx = x0 + i * (sw + 90)
        a = ease_out((t - 0.6 - i * 1.1) / 0.6)
        if a <= 0:
            continue
        lay2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay2)
        scale = 0.8 + 0.2 * a
        bx0 = sx + (sw - sw * scale) / 2
        by0 = y + (160 - 160 * scale) / 2
        dd.rounded_rectangle((bx0, by0, bx0 + sw * scale, by0 + 160 * scale), radius=24,
                             fill=GREEN_LIGHT, outline=(191, 224, 204), width=3)
        nf = ft(FONT_BOLD, 72)
        nw = dd.textlength(name, font=nf)
        dd.text((bx0 + (sw * scale - nw) / 2, by0 + 40 * scale), name, font=nf, fill=GREEN_DARK)
        img.alpha_composite(_alpha_layer(lay2, a))
    # 箭头
    if t > 3.5:
        arrow_a = ease_out((t - 3.5) / 0.5)
        lay3 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d3 = ImageDraw.Draw(lay3)
        af = ft(FONT_BOLD, 60)
        for i in range(3):
            ax = x0 + sw + i * (sw + 90) + 25
            d3.text((ax, y + 30), "→", font=af, fill=GREEN)
        img.alpha_composite(_alpha_layer(lay3, arrow_a))
    # 底部结论
    a = ease_out((t - 4.5) / 0.8)
    if a > 0:
        lay4 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d4 = ImageDraw.Draw(lay4)
        c1 = "视觉检测 + 大模型决策 双引擎，诊断可解释、处方可落地"
        cf = ft(FONT_BOLD, 50)
        wc = d4.textlength(c1, font=cf)
        d4.text((cx - wc / 2, 660), c1, font=cf, fill=INK)
        img.alpha_composite(_alpha_layer(lay4, a))
    return img.convert("RGB")


def s08_outro(t, dur):
    top, bot = (17, 66, 40), (34, 110, 66)
    img = _vgrad(top, bot)
    a = ease_out(t / (dur * 0.5))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = W // 2
    t1 = ft(FONT_BOLD, 130)
    txt = "禾目 AgriGuard"
    tw = d.textlength(txt, font=t1)
    d.text((cx - tw / 2, 380), txt, font=t1, fill=WHITE)
    sf = ft(FONT_BOLD, 56)
    stxt = "科技赋能农业，让每一株作物都被看见"
    sw = d.textlength(stxt, font=sf)
    d.text((cx - sw / 2, 580), stxt, font=sf, fill=(210, 232, 220))
    layer = _alpha_layer(layer, a)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


SCENES = [
    ("s01", s01_title),
    ("s02", s02_pain),
    ("s03", s03_upload),
    ("s04", s04_detect),
    ("s05", s05_heatmap),
    ("s06", s06_prescription),
    ("s07", s07_value),
    ("s08", s08_outro),
]


def render_all(frames_dir):
    meta = json.loads((MEDIA / "narration.json").read_text(encoding="utf-8"))
    dur_map = {m["id"]: m["dur"] for m in meta}
    timeline = []  # (scene_id, start_sec, dur_sec, tts_start_idx)
    t0 = 0.0
    n_frames = 0
    frames_dir.mkdir(parents=True, exist_ok=True)
    # 清理旧编号帧，避免残留混入
    for old in frames_dir.glob("*.png"):
        old.unlink()
    for sid, fn in SCENES:
        dur = dur_map[sid] + PRE + POST
        start = t0
        timeline.append((sid, start, dur, dur_map[sid]))
        n = int(round(dur * FPS))
        for i in range(n):
            t = i / FPS - PRE
            if t < 0:
                t = 0.0
            frame = fn(t, dur_map[sid])
            frame.save(frames_dir / f"{n_frames:05d}.png")
            n_frames += 1
        t0 += dur
        print(f"scene {sid}: {dur:.2f}s  ({n} frames)")
    (MEDIA / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    print(f"total frames {n_frames}, video {t0:.2f}s")
    return timeline, t0


def build_audio(total_sec):
    timeline = json.loads((MEDIA / "timeline.json").read_text(encoding="utf-8"))
    sr = 24000
    total = np.zeros(int(total_sec * sr), dtype=np.int16)
    for sid, start, dur, tts_dur in timeline:
        wav_path = AUDIO / f"{sid}.wav"
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getframerate() == sr and wf.getnchannels() == 1
            data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        pos = int((start + PRE) * sr)
        if pos + len(data) > len(total):
            data = data[: len(total) - pos]
        total[pos:pos + len(data)] += data
    out = MEDIA / "narr_full.wav"
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(total.tobytes())
    print("audio written:", out, f"{len(total)/sr:.2f}s")


def mux(frames_dir):
    audio = MEDIA / "narr_full.wav"
    out = MEDIA / "demo_video.mp4"
    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "%05d.png"),
        "-i", str(audio),
        "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(out),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("OUTPUT:", out)


if __name__ == "__main__":
    frames_dir = MEDIA / "frames"
    timeline, total = render_all(frames_dir)
    build_audio(total)
    mux(frames_dir)