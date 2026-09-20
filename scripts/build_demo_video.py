"""生成演示视频分镜画面（1080p）并用 ffmpeg 合成 MP4。

用法：
  python scripts/build_demo_video.py --frames-only   # 只生成画面帧
  python scripts/build_demo_video.py                 # 生成帧并合成视频
"""
import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
FRAMES = MEDIA / "frames"
SCREENS = MEDIA / "screens"

W, H = 1920, 1080
FPS = 30

FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = "C:/Windows/Fonts/msyh.ttc"

GREEN = (46, 125, 79)
GREEN_DARK = (31, 94, 58)
GREEN_LIGHT = (234, 245, 238)
BG = (237, 245, 239)
INK = (31, 41, 51)
MUTED = (100, 116, 139)
WHITE = (255, 255, 255)
GOLD = (196, 154, 66)


def ft(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) <= max_w:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def new_canvas(bg=BG):
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def vgradient(top, bottom):
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img


def text_block(canvas, draw, text, fnt, color, x, y, max_w=None, line_gap=None, align="left"):
    if max_w is None:
        max_w = W - 240
    lines = wrap(draw, text, fnt, max_w)
    gap = line_gap if line_gap is not None else int(fnt.size * 0.38)
    yy = y
    for ln in lines:
        w = draw.textlength(ln, font=fnt)
        xx = x - w / 2 if align == "center" else x
        draw.text((xx, yy), ln, font=fnt, fill=color)
        yy += fnt.size + gap
    return yy


def paste_fit(canvas, img, max_w, max_h, cx=None, cy=None):
    ratio = min(max_w / img.width, max_h / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    resized = img.resize((nw, nh), Image.LANCZOS)
    x = int((W - nw) / 2) if cx is None else int(cx - nw / 2)
    y = int((H - nh) / 2) if cy is None else int(cy - nh / 2)
    canvas.paste(resized, (x, y))
    return x, y, nw, nh


def caption(canvas, draw, text, y=None):
    fnt = ft(FONT_BOLD, 44)
    yy = y if y is not None else H - 130
    cw = draw.textlength(text, font=fnt)
    # 半透明底条
    bar = Image.new("RGBA", (W, 120), (31, 94, 58, 210))
    canvas.paste(bar, (0, yy - 34), bar)
    draw.text(((W - cw) / 2, yy), text, font=fnt, fill=WHITE)


def round_card(canvas, draw, box, fill, outline=None, radius=28):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=3 if outline else 0)


# ---------- 各分镜 ----------

def s01_title():
    top = (17, 66, 40)
    bottom = (34, 110, 66)
    canvas = vgradient(top, bottom)
    draw = ImageDraw.Draw(canvas)
    # 顶部徽标
    badge_ft = ft(FONT_BOLD, 30)
    badge = "AI 辅助制作"
    bw = draw.textlength(badge, font=badge_ft)
    draw.rounded_rectangle((W / 2 - bw / 2 - 30, 130, W / 2 + bw / 2 + 30, 130 + 62), radius=31, outline=(191, 224, 204), width=2)
    draw.text((W / 2 - bw / 2, 143), badge, font=badge_ft, fill=(220, 240, 228))
    # 主标题
    t1 = ft(FONT_BOLD, 150)
    t2 = ft(FONT_REG, 110)
    s1 = "禾目"
    s2 = "AgriGuard"
    w1 = draw.textlength(s1, font=t1)
    w2 = draw.textlength(s2, font=t2)
    total = w1 + w2 + 24
    x = (W - total) / 2
    draw.text((x, 280), s1, font=t1, fill=WHITE)
    draw.text((x + w1 + 24, 322), s2, font=t2, fill=(178, 224, 194))
    # 副标题
    sub = "作物病虫害智能诊断与精准处方系统"
    sub_ft = ft(FONT_BOLD, 52)
    sw = draw.textlength(sub, font=sub_ft)
    draw.text(((W - sw) / 2, 520), sub, font=sub_ft, fill=(232, 244, 237))
    # 分隔线
    draw.line((W / 2 - 90, 640, W / 2 + 90, 640), fill=(191, 224, 204), width=3)
    tag = "拍一张病叶 · 秒出诊断与处方"
    tag_ft = ft(FONT_REG, 40)
    tw = draw.textlength(tag, font=tag_ft)
    draw.text(((W - tw) / 2, 680), tag, font=tag_ft, fill=(200, 224, 210))
    return canvas


def s02_pain():
    canvas, draw = new_canvas(WHITE)
    label_ft = ft(FONT_BOLD, 40)
    draw.rounded_rectangle((120, 120, 120 + 210, 120 + 70), radius=35, fill=GREEN_LIGHT)
    draw.text((120 + 60, 138), "行业痛点", font=label_ft, fill=GREEN_DARK)
    title = "专业植保资源稀缺，农户“看病难、开方难”"
    title_ft = ft(FONT_BOLD, 66)
    text_block(canvas, draw, title, title_ft, INK, W / 2, 300, align="center")
    items = [
        "基层缺专家：病害诊断依赖经验，误判、延误常见",
        "凭感觉用药：盲目施药，效果差、残留高、成本增",
        "知识门槛高：优质防治方案难以触达普通种植者",
    ]
    item_ft = ft(FONT_REG, 46)
    yy = 500
    for it in items:
        draw.ellipse((140, yy + 16, 140 + 16, yy + 32), fill=GREEN)
        text_block(canvas, draw, it, item_ft, INK, 220, yy, max_w=W - 360, align="left")
        yy += 130
    return canvas


def s03_home():
    canvas, draw = new_canvas(GREEN_LIGHT)
    home = Image.open(SCREENS / "01_home.png").convert("RGB")
    paste_fit(canvas, home, 1700, 900)
    caption(canvas, draw, "拍一张病叶照片，秒出诊断与防治处方")
    return canvas


def s04_detect():
    canvas, draw = new_canvas(GREEN_LIGHT)
    round_card(canvas, draw, (240, 150, W - 240, H - 150), WHITE, outline=(226, 232, 240))
    # 左侧叶片缩略图
    leaf = Image.open(MEDIA / "leaf_original.jpg").convert("RGB")
    lw = 460
    ratio = lw / leaf.width
    leaf_s = leaf.resize((lw, int(leaf.height * ratio)), Image.LANCZOS)
    canvas.paste(leaf_s, (280, 260))
    # 右侧结果
    rx = 820
    draw.text((rx, 240), "诊断结果", font=ft(FONT_BOLD, 42), fill=MUTED)
    name_ft = ft(FONT_BOLD, 92)
    draw.text((rx, 330), "番茄 · 早疫病", font=name_ft, fill=GREEN_DARK)
    conf_ft = ft(FONT_BOLD, 58)
    draw.text((rx, 470), "识别置信度 100.0%", font=conf_ft, fill=GREEN)
    top_ft = ft(FONT_REG, 40)
    draw.text((rx, 610), "Top 3 候选：", font=top_ft, fill=MUTED)
    cand = "早疫病 100%  ·  晚疫病 0%  ·  葡萄黑腐病 0%"
    draw.text((rx, 680), cand, font=top_ft, fill=INK)
    draw.text((rx, 820), "YOLO 视觉引擎 · 30 轮训练 · 38 类病害", font=ft(FONT_REG, 36), fill=MUTED)
    return canvas


def s05_heatmap():
    canvas, draw = new_canvas(WHITE)
    title = "Grad-CAM 病灶定位：让 AI 的判断一目了然"
    title_ft = ft(FONT_BOLD, 60)
    tw = draw.textlength(title, font=title_ft)
    draw.text(((W - tw) / 2, 70), title, font=title_ft, fill=GREEN_DARK)
    orig = Image.open(MEDIA / "leaf_original.jpg").convert("RGB")
    heat = Image.open(MEDIA / "heatmap.jpg").convert("RGB")
    box_w = 700
    # 原图
    ratio = min(box_w / orig.width, 640 / orig.height)
    o = orig.resize((int(orig.width * ratio), int(orig.height * ratio)), Image.LANCZOS)
    x1 = 80
    canvas.paste(o, (x1, 210))
    draw.text((x1 + (box_w - draw.textlength("原图", font=ft(FONT_BOLD, 44))) / 2, 870), "原图", font=ft(FONT_BOLD, 44), fill=MUTED)
    # 热力图
    hh = heat.resize((int(heat.width * ratio), int(heat.height * ratio)), Image.LANCZOS)
    x2 = W - 80 - box_w
    canvas.paste(hh, (x2, 210))
    draw.text((x2 + (box_w - draw.textlength("病灶热力图", font=ft(FONT_BOLD, 44))) / 2, 870), "病灶热力图", font=ft(FONT_BOLD, 44), fill=GREEN_DARK)
    caption(canvas, draw, "高亮区域即模型识别的染病部位", y=950)
    return canvas


def s06_prescription():
    canvas, draw = new_canvas(GREEN_LIGHT)
    title = "大语言模型生成个性化防治处方"
    title_ft = ft(FONT_BOLD, 58)
    tw = draw.textlength(title, font=title_ft)
    draw.text(((W - tw) / 2, 60), title, font=title_ft, fill=GREEN_DARK)
    round_card(canvas, draw, (140, 170, 930, 940), WHITE, outline=(226, 232, 240))
    round_card(canvas, draw, (960, 170, W - 140, 940), WHITE, outline=(226, 232, 240))
    # 左卡
    lx = 190
    lw = 690
    draw.text((lx, 210), "病原诊断", font=ft(FONT_BOLD, 40), fill=GREEN)
    text_block(canvas, draw, "番茄 · 早疫病（真菌性病害，链格孢属）", ft(FONT_REG, 40), INK, lx, 285, max_w=lw, align="left")
    draw.text((lx, 460), "化学用药", font=ft(FONT_BOLD, 40), fill=GREEN)
    text_block(canvas, draw, "68% 精甲霜·锰锌 600 倍液；或 50% 异菌脲 1000 倍液，安全间隔期 3–7 天", ft(FONT_REG, 40), INK, lx, 535, max_w=lw, align="left")
    draw.text((lx, 730), "生物防治", font=ft(FONT_BOLD, 40), fill=GREEN)
    text_block(canvas, draw, "枯草芽孢杆菌 500 倍液，5–7 天一次，连喷 2 次", ft(FONT_REG, 40), INK, lx, 805, max_w=lw, align="left")
    # 右卡
    rx = 1010
    rw = 730
    draw.text((rx, 210), "日常管理", font=ft(FONT_BOLD, 40), fill=GREEN)
    text_block(canvas, draw, "摘除病叶老叶集中处理；改漫灌为滴灌；及时通风排湿；整枝打杈保证透光；收获后清园深翻", ft(FONT_REG, 40), INK, rx, 285, max_w=rw, align="left")
    draw.text((rx, 560), "一句话结论", font=ft(FONT_BOLD, 40), fill=GREEN)
    text_block(canvas, draw, "早发现、早防治、科学用药，把损失降到最低", ft(FONT_BOLD, 48), GREEN_DARK, rx, 640, max_w=rw, align="left")
    return canvas


def s07_value():
    canvas, draw = new_canvas(WHITE)
    draw.text((W / 2 - 180, 100), "核心价值", font=ft(FONT_BOLD, 52), fill=GREEN_DARK)
    steps = ["识别", "定位", "评估", "处方"]
    step_ft = ft(FONT_BOLD, 72)
    arrow_ft = ft(FONT_BOLD, 60)
    xs = [250, 660, 1070, 1480]
    for sx, name in zip(xs, steps):
        round_card(canvas, draw, (sx, 260, sx + 300, 440), GREEN_LIGHT, outline=(191, 224, 204))
        tw = draw.textlength(name, font=step_ft)
        draw.text((sx + 150 - tw / 2, 315), name, font=step_ft, fill=GREEN_DARK)
    for ax, ay in [(560, 320), (970, 320), (1380, 320)]:
        draw.text((ax, ay), "→", font=arrow_ft, fill=GREEN)
    desc = "从“只识别什么病”升级为“识别 → 定位 → 评估 → 处方”的完整闭环"
    text_block(canvas, draw, desc, ft(FONT_REG, 48), INK, W / 2, 600, align="center")
    line2 = "视觉检测 + 大模型决策 双引擎，诊断可解释、处方可落地"
    text_block(canvas, draw, line2, ft(FONT_BOLD, 46), GREEN_DARK, W / 2, 780, align="center")
    return canvas


def s08_outro():
    top = (17, 66, 40)
    bottom = (34, 110, 66)
    canvas = vgradient(top, bottom)
    draw = ImageDraw.Draw(canvas)
    t = "禾目 AgriGuard"
    fnt = ft(FONT_BOLD, 130)
    tw = draw.textlength(t, font=fnt)
    draw.text(((W - tw) / 2, 360), t, font=fnt, fill=WHITE)
    sub = "智慧农业 · 减肥减药 · 数字乡村"
    sub_ft = ft(FONT_BOLD, 56)
    sw = draw.textlength(sub, font=sub_ft)
    draw.text(((W - sw) / 2, 560), sub, font=sub_ft, fill=(200, 224, 210))
    return canvas


SCENES = [
    ("s01", s01_title, 4.0),
    ("s02", s02_pain, 5.0),
    ("s03", s03_home, 6.0),
    ("s04", s04_detect, 7.0),
    ("s05", s05_heatmap, 8.0),
    ("s06", s06_prescription, 10.0),
    ("s07", s07_value, 7.0),
    ("s08", s08_outro, 4.0),
]


def build_frames():
    FRAMES.mkdir(parents=True, exist_ok=True)
    for name, fn, _dur in SCENES:
        img = fn()
        img.save(FRAMES / f"{name}.png")
        print(f"frame {name}.png")


def build_video():
    FRAMES.mkdir(parents=True, exist_ok=True)
    out = MEDIA / "demo_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"avc1")
    vw = cv2.VideoWriter(str(out), fourcc, FPS, (W, H))
    if not vw.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        vw = cv2.VideoWriter(str(out), fourcc, FPS, (W, H))
    if not vw.isOpened():
        raise RuntimeError("cv2.VideoWriter 打开失败，无法写入 MP4")

    for name, fn, dur in SCENES:
        base = fn().convert("RGB")
        arr = np.asarray(base)[:, :, ::-1].copy()  # RGB -> BGR
        n = int(round(dur * FPS))
        static = name in ("s01", "s08")
        if static:
            for _ in range(n):
                vw.write(arr)
            continue
        big = cv2.resize(arr, (W * 2, H * 2), interpolation=cv2.INTER_CUBIC)
        zoom_end = 1.16
        for i in range(n):
            z = 1.0 + (zoom_end - 1.0) * i / max(1, n - 1)
            cw, ch = int(W * 2 / z), int(H * 2 / z)
            x0 = (W * 2 - cw) // 2
            y0 = (H * 2 - ch) // 2
            crop = big[y0:y0 + ch, x0:x0 + cw]
            frame = cv2.resize(crop, (W, H), interpolation=cv2.INTER_LINEAR)
            vw.write(frame)
        print(f"scene {name} done ({n} frames)")

    vw.release()
    print("OUTPUT:", out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-only", action="store_true")
    args = ap.parse_args()
    if args.frames_only:
        build_frames()
    else:
        build_video()