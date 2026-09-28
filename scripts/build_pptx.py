"""生成产品说明 PPT（16:9，绿色农业科技风）。"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent
MAT = ROOT / "参赛材料"
ASSET = MAT / "assets"
MEDIA = ROOT / "media"
OUT = MAT / "产品说明PPT.pptx"

# ---------------- 主题色 ----------------
PRIMARY = "1F5E3A"
PRIMARY_DARK = "123A26"
SECONDARY = "2E7D4F"
MINT = "86EFAC"
MINT_SOFT = "D8F3E2"
CYAN = "0E7490"
CYAN_LIGHT = "06B6D4"
LIGHT_BG = "F4F8F5"
CARD = "FFFFFF"
INK = "1F2937"
MUTED = "5B6B78"
GOLD = "C49A42"
LINE = "DCE8E0"

TITLE_FONT = "微软雅黑"
BODY_FONT = "微软雅黑"

SW = Inches(13.333)
SH = Inches(7.5)
M = Inches(0.6)
CW = Inches(13.333 - 1.2)
CH = Inches(7.5 - 1.2)


def color(h):
    return RGBColor.from_string(h)


def _set_ea(run, name):
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = rPr.makeelement(qn(tag), {})
            rPr.append(e)
        e.set("typeface", name)


def style(run, size, bold=False, c=INK, name=BODY_FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color(c)
    run.font.name = name
    _set_ea(run, name)


def rect(slide, x, y, w, h, fill=None, line=None, line_w=1.0, radius=None, shape=MSO_SHAPE.RECTANGLE):
    sp = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = color(fill)
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = color(line)
        sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    return sp


def txt(slide, x, y, w, h, lines, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
        space_after=6, line_spacing=1.0):
    """lines: list of dicts {runs:[(text,{...})], ...} 或简单字符串列表。"""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    if isinstance(lines, str):
        lines = [lines]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        if isinstance(ln, str):
            r = p.add_run()
            r.text = ln
            style(r, 16, False, INK)
        else:
            runs = ln.get("runs", [])
            for rt in runs:
                r = p.add_run()
                r.text = rt[0]
                opt = rt[1] if len(rt) > 1 else {}
                style(r, opt.get("size", 16), opt.get("bold", False),
                      opt.get("c", INK), opt.get("name", BODY_FONT))
    return tb


def title_bar(slide, num, title, subtitle=None):
    rect(slide, M, Inches(0.55), Inches(0.18), Inches(0.72), fill=PRIMARY)
    txt(slide, Inches(0.95), Inches(0.5), Inches(11.5), Inches(0.9),
        [{"runs": [(title, {"size": 26, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    if subtitle:
        txt(slide, Inches(0.97), Inches(1.12), Inches(11.6), Inches(0.4),
            [{"runs": [(subtitle, {"size": 12.5, "c": MUTED})]}])
    # 章节序号
    txt(slide, Inches(12.15), Inches(0.5), Inches(0.9), Inches(0.6),
        [{"runs": [(num, {"size": 15, "bold": True, "c": MINT})]}], align=PP_ALIGN.RIGHT)


def footer(slide, idx):
    txt(slide, M, Inches(7.08), Inches(6), Inches(0.35),
        [{"runs": [("禾目 AgriGuard · 智慧农业", {"size": 9, "c": MUTED})]}])
    txt(slide, Inches(11.7), Inches(7.08), Inches(1.0), Inches(0.35),
        [{"runs": [(f"{idx:02d}", {"size": 9, "c": MUTED})]}], align=PP_ALIGN.RIGHT)


def chip(slide, x, y, w, h, text, fill=MINT_SOFT, tc=PRIMARY, size=12, bold=True):
    sp = rect(slide, x, y, w, h, fill=fill, radius=0.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    tf = sp.text_frame
    tf.word_wrap = False
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    style(r, size, bold, tc)
    return sp


def icon_circle(slide, x, y, d, glyph, fill=PRIMARY, tc="FFFFFF", size=18):
    c = rect(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = glyph
    style(r, size, True, tc)
    return c


def arrow_right(slide, x, y, w, h, c=SECONDARY):
    return rect(slide, x, y, w, h, fill=c, shape=MSO_SHAPE.RIGHT_ARROW)


def card(slide, x, y, w, h, fill=CARD, line=LINE, radius=0.08):
    return rect(slide, x, y, w, h, fill=fill, line=line, line_w=1.0,
                radius=radius, shape=MSO_SHAPE.ROUNDED_RECTANGLE)


def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w is not None:
        kw["width"] = w
    if h is not None:
        kw["height"] = h
    return slide.shapes.add_picture(str(path), x, y, **kw)


prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]


def new_slide(bg=LIGHT_BG):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, SW, SH, fill=bg)
    return s


# ================= Slide 1 封面 =================
s = prs.slides.add_slide(BLANK)
pic(s, ASSET / "cover_bg.jpg", 0, 0, w=SW, h=SH)
rect(s, 0, 0, SW, Inches(0.14), fill=MINT)
pic(s, ASSET / "logo_512x512.png", Inches(0.9), Inches(0.9), w=Inches(1.1))
txt(s, Inches(2.15), Inches(1.02), Inches(9), Inches(0.9),
    [{"runs": [("禾目 AgriGuard", {"size": 24, "bold": True, "c": "FFFFFF", "name": TITLE_FONT})]}])
txt(s, Inches(0.9), Inches(2.7), Inches(11.5), Inches(1.3),
    [{"runs": [("作物病虫害智能诊断与精准处方系统", {"size": 40, "bold": True, "c": "FFFFFF", "name": TITLE_FONT})]}])
rect(s, Inches(0.92), Inches(4.15), Inches(1.6), Inches(0.06), fill=MINT)
txt(s, Inches(0.9), Inches(4.45), Inches(11), Inches(0.6),
    [{"runs": [("拍一张病叶，秒出 AI 诊断与防治处方", {"size": 20, "c": MINT})]}])
txt(s, Inches(0.9), Inches(6.4), Inches(10), Inches(0.5),
    [{"runs": [("禾目 团队  ·  iCAN 大学生创新创业大赛（创新赛道）", {"size": 13, "c": "BFE6CF"})]}])
chip(s, Inches(11.0), Inches(6.55), Inches(1.75), Inches(0.44), "AI 辅助制作", fill="1D5A38", tc="BFE6CF", size=11)

# ================= Slide 2 目录 =================
s = new_slide()
title_bar(s, "目录", "CONTENTS")
toc = [
    ("01", "项目概述", "背景 · 痛点 · 产品定位"),
    ("02", "产品功能与操作流程", "核心闭环 · 真实操作演示"),
    ("03", "技术要点", "识别 · 定位 · 处方三大引擎"),
    ("04", "应用场景", "四类目标用户群体"),
    ("05", "创新点与应用价值", "差异化优势 · 社会意义"),
    ("06", "团队介绍", "成员与分工"),
]
cx0 = Inches(0.9)
cw = Inches(5.9)
ch = Inches(1.55)
gx = Inches(0.28)
gy = Inches(0.26)
for i, (num, t, d) in enumerate(toc):
    col = i % 2
    row = i // 2
    x = cx0 + col * (cw + gx)
    y = Inches(1.7) + row * (ch + gy)
    card(s, x, y, cw, ch)
    rect(s, x, y, Inches(0.14), ch, fill=SECONDARY)
    txt(s, x + Inches(0.5), y + Inches(0.28), Inches(1.2), Inches(0.8),
        [{"runs": [(num, {"size": 30, "bold": True, "c": MINT})]}])
    txt(s, x + Inches(1.5), y + Inches(0.3), Inches(4.2), Inches(0.6),
        [{"runs": [(t, {"size": 19, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    txt(s, x + Inches(1.5), y + Inches(0.88), Inches(4.2), Inches(0.5),
        [{"runs": [(d, {"size": 12, "c": MUTED})]}])
footer(s, 2)

# ================= Slide 3 行业痛点 =================
s = new_slide()
title_bar(s, "01", "行业痛点：看病难、开方难", "农业生产中的真实困境")
pains = [
    ("看病难", "病虫害诊断高度依赖植保专家经验，基层农户缺少专业判断能力，常凭感觉识别。"),
    ("开方难", "缺乏科学用药指导，盲目加大剂量，导致防治效果差、农药残留高、成本上升。"),
    ("资源缺", "专业植保资源稀缺且分布不均，难以规模化覆盖广大中小种植者与农技一线。"),
]
px0 = Inches(0.9)
pw = Inches(3.7)
ph = Inches(3.4)
gx = Inches(0.4)
y = Inches(1.9)
for i, (t, d) in enumerate(pains):
    x = px0 + i * (pw + gx)
    card(s, x, y, pw, ph, line=LINE)
    icon_circle(s, x + Inches(0.35), y + Inches(0.4), Inches(0.85), ["!", "药", "!"][i], fill=SECONDARY, size=20)
    txt(s, x + Inches(0.35), y + Inches(1.5), pw - Inches(0.7), Inches(0.7),
        [{"runs": [(t, {"size": 22, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    txt(s, x + Inches(0.35), y + Inches(2.15), pw - Inches(0.7), Inches(1.1),
        [{"runs": [(d, {"size": 14, "c": INK})]}], line_spacing=1.15)
# 底部结论
rect(s, Inches(0.9), Inches(5.7), Inches(11.55), Inches(0.9), fill=MINT_SOFT, radius=0.12, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
txt(s, Inches(1.3), Inches(5.86), Inches(10.8), Inches(0.6),
    [{"runs": [("亟需一套低成本、易上手、可规模化的智能诊断工具", {"size": 17, "bold": True, "c": PRIMARY})]}], align=PP_ALIGN.CENTER)
footer(s, 3)

# ================= Slide 4 产品定位 =================
s = new_slide()
title_bar(s, "01", "产品定位：禾目 AgriGuard，让专业植保触手可及", "面向每一位普通种植者的 AI 作物医生")
rect(s, Inches(0.9), Inches(1.9), Inches(11.55), Inches(1.5), fill=PRIMARY, radius=0.1, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
txt(s, Inches(1.4), Inches(2.1), Inches(10.6), Inches(1.1),
    [{"runs": [("拍一张病叶，秒出「是什么病 + 怎么治」的 AI 处方", {"size": 24, "bold": True, "c": "FFFFFF", "name": TITLE_FONT})]}])
txt(s, Inches(1.4), Inches(2.85), Inches(10.6), Inches(0.5),
    [{"runs": [("上传/拍摄叶片 → 病害识别 → 染病区域定位 → 严重度评估 → 个性化防治处方", {"size": 13, "c": MINT})]}])
vals = [
    ("秒级响应", "数秒内完成识别与处方"),
    ("可解释", "热力图高亮染病区域"),
    ("可落地", "处方包含药剂/用量/间隔期"),
    ("零门槛", "普通电脑即可运行部署"),
]
vy = Inches(3.8)
vw = Inches(2.7)
vg = Inches(0.25)
for i, (t, d) in enumerate(vals):
    x = Inches(0.9) + i * (vw + vg)
    card(s, x, vy, vw, Inches(2.1), line=LINE)
    rect(s, x + Inches(0.3), vy + Inches(0.35), Inches(0.5), Inches(0.5), fill=MINT, radius=0.3, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    txt(s, x + Inches(0.3), vy + Inches(1.05), vw - Inches(0.6), Inches(0.6),
        [{"runs": [(t, {"size": 17, "bold": True, "c": PRIMARY_DARK})]}])
    txt(s, x + Inches(0.3), vy + Inches(1.55), vw - Inches(0.6), Inches(0.5),
        [{"runs": [(d, {"size": 11.5, "c": MUTED})]}])
footer(s, 4)

# ================= Slide 5 核心功能闭环 =================
s = new_slide()
title_bar(s, "02", "核心功能闭环：从识别到处方的完整链路", "视觉检测 + 大模型决策双引擎驱动")
steps = [
    ("病叶上传", "拍摄/上传照片"),
    ("病害识别", "YOLO 识别 Top3"),
    ("病灶定位", "Grad-CAM 热力图"),
    ("严重度评估", "结构化评估"),
    ("智能处方", "大模型个性化建议"),
]
n = len(steps)
bw = Inches(1.95)
bh = Inches(2.3)
gap = Inches(0.5)
total = n * bw + (n - 1) * gap
x0 = (SW - total) / 2
y = Inches(2.2)
for i, (t, d) in enumerate(steps):
    x = x0 + i * (bw + gap)
    card(s, x, y, bw, bh, line=LINE)
    icon_circle(s, x + Inches(0.68), y + Inches(0.35), Inches(0.6), ["①", "②", "③", "④", "⑤"][i], fill=SECONDARY, size=16)
    txt(s, x + Inches(0.15), y + Inches(1.2), bw - Inches(0.3), Inches(0.6),
        [{"runs": [(t, {"size": 16, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}], align=PP_ALIGN.CENTER)
    txt(s, x + Inches(0.15), y + Inches(1.72), bw - Inches(0.3), Inches(0.5),
        [{"runs": [(d, {"size": 11, "c": MUTED})]}], align=PP_ALIGN.CENTER)
    if i < n - 1:
        arrow_right(s, x + bw + Inches(0.02), y + Inches(1.0), gap - Inches(0.04), Inches(0.35))
txt(s, Inches(0.9), Inches(5.3), Inches(11.55), Inches(1.1),
    [{"runs": [("零门槛：", {"size": 15, "bold": True, "c": PRIMARY}),
               ("用户只需一步操作，后端自动完成「识别 → 定位 → 评估 → 处方」全程，结果以通俗语言呈现。", {"size": 15, "c": INK})]}],
    line_spacing=1.2)
footer(s, 5)

# ================= Slide 6 操作流程（真实截图） =================
s = new_slide()
title_bar(s, "02", "操作流程：真实运行效果", "三步完成一次作物健康诊断")
flows = [
    ("① 上传病叶", "点击或拖拽上传一张病叶照片，支持 jpg / png。"),
    ("② 秒级诊断", "视觉引擎识别病害类型与置信度，Top3 清晰呈现。"),
    ("③ 可视化定位", "Grad-CAM 热力图高亮染病区域，判断有据可循。"),
    ("④ 智能处方", "大模型生成包含药剂、用量、间隔期的防治建议。"),
]
fy = Inches(1.95)
fw = Inches(4.6)
for i, (t, d) in enumerate(flows):
    y = fy + i * Inches(1.18)
    card(s, Inches(0.9), y, fw, Inches(1.0))
    icon_circle(s, Inches(1.15), y + Inches(0.27), Inches(0.5), str(i + 1), fill=SECONDARY, size=14)
    txt(s, Inches(1.85), y + Inches(0.12), Inches(3.5), Inches(0.5),
        [{"runs": [(t, {"size": 15, "bold": True, "c": PRIMARY_DARK})]}])
    txt(s, Inches(1.85), y + Inches(0.5), Inches(3.5), Inches(0.45),
        [{"runs": [(d, {"size": 11.5, "c": MUTED})]}], line_spacing=1.05)
# 右侧截图
shot = MEDIA / "screens" / "02_result.png"
pic(s, shot, Inches(5.85), Inches(1.9), w=Inches(6.55))
footer(s, 6)

# ================= Slide 7 技术架构总览 =================
s = new_slide()
title_bar(s, "03", "技术架构：视觉检测 + 大模型决策双引擎", "从浏览器到模型与处方的完整链路")
# 三层
def arch_box(x, y, w, h, title, sub, fill, tc="FFFFFF", subc="DCF5E5"):
    rect(s, x, y, w, h, fill=fill, radius=0.1, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    txt(s, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5), Inches(0.5),
        [{"runs": [(title, {"size": 15, "bold": True, "c": tc, "name": TITLE_FONT})]}], align=PP_ALIGN.CENTER)
    txt(s, x + Inches(0.2), y + Inches(0.62), w - Inches(0.4), Inches(0.5),
        [{"runs": [(sub, {"size": 10.5, "c": subc})]}], align=PP_ALIGN.CENTER)

# 前端层
arch_box(Inches(0.9), Inches(1.9), Inches(11.55), Inches(0.95), "展示层 · 原生 Web 前端", "HTML / CSS / JS —— 上传、结果、热力图、处方", SECONDARY)
# 后端层
arch_box(Inches(0.9), Inches(3.05), Inches(11.55), Inches(0.95), "服务层 · FastAPI 接口", "/predict 接收图片，编排识别 → 定位 → 处方全流程", CYAN)
# 引擎层（三卡）
engines = [
    ("病害识别引擎", "YOLO11n-cls\n38 类 · 99.7%", PRIMARY),
    ("可视化解译", "Grad-CAM\n染病区域高亮", PRIMARY),
    ("精准处方引擎", "通义千问 qwen-plus\n结构化处方", PRIMARY),
]
ew = Inches(3.7)
eg = Inches(0.22)
ey = Inches(4.2)
for i, (t, d, f) in enumerate(engines):
    x = Inches(0.9) + i * (ew + eg)
    card(s, x, ey, ew, Inches(1.9), line=LINE)
    rect(s, x + Inches(0.28), ey + Inches(0.3), Inches(0.5), Inches(0.5), fill=MINT_SOFT, radius=0.3, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    txt(s, x + Inches(0.28), ey + Inches(0.3), Inches(0.5), Inches(0.5),
        [{"runs": [(["识", "定", "方"][i], {"size": 15, "bold": True, "c": PRIMARY})]}], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    txt(s, x + Inches(0.95), ey + Inches(0.22), ew - Inches(1.2), Inches(0.6),
        [{"runs": [(t, {"size": 15, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    txt(s, x + Inches(0.95), ey + Inches(0.82), ew - Inches(1.2), Inches(0.9),
        [{"runs": [(d, {"size": 11.5, "c": MUTED})]}], line_spacing=1.05)
footer(s, 7)

# ================= Slide 8 病害识别引擎 =================
s = new_slide()
title_bar(s, "03", "病害识别引擎：YOLO11n-cls 深度学习模型", "38 类作物病害与健康状态识别")
stats = [("99.7%", "Top-1 准确率"), ("38 类", "病害/健康类别"), ("60,343 张", "PlantVillage 数据")]
sx0 = Inches(0.9)
sw_box = Inches(3.7)
sg = Inches(0.22)
for i, (v, l) in enumerate(stats):
    x = sx0 + i * (sw_box + sg)
    card(s, x, Inches(1.9), sw_box, Inches(1.3), line=LINE)
    txt(s, x + Inches(0.3), Inches(2.0), sw_box - Inches(0.6), Inches(0.7),
        [{"runs": [(v, {"size": 30, "bold": True, "c": SECONDARY})]}], align=PP_ALIGN.CENTER)
    txt(s, x + Inches(0.3), Inches(2.75), sw_box - Inches(0.6), Inches(0.4),
        [{"runs": [(l, {"size": 12, "c": MUTED})]}], align=PP_ALIGN.CENTER)
pic(s, ASSET / "top1_curve.png", Inches(0.9), Inches(3.3), w=Inches(5.4))
# 右侧真实样本对比
txt(s, Inches(6.6), Inches(3.22), Inches(5.8), Inches(0.4),
    [{"runs": [("真实训练样本", {"size": 16, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
pic(s, ASSET / "sample_disease.png", Inches(6.6), Inches(3.72), w=Inches(2.55))
pic(s, ASSET / "sample_healthy.png", Inches(9.55), Inches(3.72), w=Inches(2.55))
txt(s, Inches(6.6), Inches(6.32), Inches(2.55), Inches(0.35),
    [{"runs": [("病叶样张 · 早疫病", {"size": 11, "c": MUTED})]}], align=PP_ALIGN.CENTER)
txt(s, Inches(9.55), Inches(6.32), Inches(2.55), Inches(0.35),
    [{"runs": [("健康叶样张", {"size": 11, "c": MUTED})]}], align=PP_ALIGN.CENTER)
txt(s, Inches(0.9), Inches(6.78), Inches(11.55), Inches(0.4),
    [{"runs": [("YOLO11n-cls · 30 epoch 收敛 · Top-1 96.6%→99.7% · 验证损失持续下降 · 38 类中英文完整映射 · train/val 8:2",
                {"size": 12, "c": INK})]}])
footer(s, 8)

# ================= Slide 9 Grad-CAM 定位 =================
s = new_slide()
title_bar(s, "03", "可视化解译：Grad-CAM 病灶定位", "让 AI 的判断「有图有真相」")
pic(s, ASSET / "heatmap_hi.png", Inches(0.9), Inches(2.2), w=Inches(4.2))
txt(s, Inches(0.9), Inches(6.05), Inches(4.2), Inches(0.5),
    [{"runs": [("Grad-CAM 热力图（红色为高关注区域）", {"size": 11, "c": MUTED})]}], align=PP_ALIGN.CENTER)
txt(s, Inches(5.6), Inches(2.2), Inches(7.0), Inches(0.6),
    [{"runs": [("为什么需要可解释性？", {"size": 18, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
exp = [
    "纯概率结果难以让人信服，热力图让用户直观看到模型「看哪儿」。",
    "系统在分类头线性层（原始 logits，跳过 softmax）反向传播梯度，规避 softmax 饱和引发的梯度消失，得到稳定清晰的病灶热图。",
    "病灶区域高亮与诊断结果相互印证，提升基层用户对 AI 结论的信任。",
]
txt(s, Inches(5.6), Inches(2.9), Inches(7.0), Inches(2.6),
    [{"runs": [(e, {"size": 14, "c": INK})]} for e in exp], line_spacing=1.3)
chip(s, Inches(5.6), Inches(5.65), Inches(2.6), Inches(0.5), "可解释 AI", fill=MINT_SOFT, tc=PRIMARY, size=13)
chip(s, Inches(8.4), Inches(5.65), Inches(2.6), Inches(0.5), "判断可信", fill=MINT_SOFT, tc=PRIMARY, size=13)
footer(s, 9)

# ================= Slide 10 精准处方引擎 =================
s = new_slide()
title_bar(s, "03", "精准处方引擎：大模型生成个性化防治方案", "结构化输出，减量增效、安全可落地")
rect(s, Inches(0.9), Inches(1.9), Inches(11.55), Inches(1.05), fill=MINT_SOFT, radius=0.1, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
txt(s, Inches(1.3), Inches(2.0), Inches(10.8), Inches(0.5),
    [{"runs": [("通义千问 qwen-plus", {"size": 17, "bold": True, "c": PRIMARY}),
               ("  ——  以「资深植物医生」视角，结合病害与严重度输出个性化处方", {"size": 14, "c": INK})]}])
fields = [
    ("严重程度", "综合判断病情等级"),
    ("生物防治", "优先绿色防控手段"),
    ("化学用药", "推荐药剂 · 减量增效"),
    ("安全间隔期", "明确采收安全期"),
    ("日常管理", "水肥与田间卫生提示"),
]
fw_ = Inches(2.15)
fg = Inches(0.2)
fx0 = Inches(0.9)
fy0 = Inches(3.25)
for i, (t, d) in enumerate(fields):
    x = fx0 + (i % 5) * (fw_ + fg)
    card(s, x, fy0, fw_, Inches(1.9), line=LINE)
    icon_circle(s, x + Inches(0.78), fy0 + Inches(0.3), Inches(0.6), str(i + 1), fill=SECONDARY, size=14)
    txt(s, x + Inches(0.15), fy0 + Inches(1.05), fw_ - Inches(0.3), Inches(0.5),
        [{"runs": [(t, {"size": 13.5, "bold": True, "c": PRIMARY_DARK})]}], align=PP_ALIGN.CENTER)
    txt(s, x + Inches(0.15), fy0 + Inches(1.5), fw_ - Inches(0.3), Inches(0.4),
        [{"runs": [(d, {"size": 10.5, "c": MUTED})]}], align=PP_ALIGN.CENTER)
txt(s, Inches(0.9), Inches(5.5), Inches(11.55), Inches(1.0),
    [{"runs": [("容错设计：", {"size": 14, "bold": True, "c": PRIMARY}),
               ("未配置密钥或接口异常时自动回落内置模板处方；健康叶片输出「无需防治」专门建议，保证任何网络环境下结果稳定可返回。", {"size": 14, "c": INK})]}],
    line_spacing=1.2)
footer(s, 10)

# ================= Slide 11 关键技术要点 =================
s = new_slide()
title_bar(s, "03", "关键技术要点与工程实践", "针对真实问题的四个工程突破")
points = [
    ("中文类别映射", "38 类真实类名→中文精确映射，经脚本校验 0 缺失 / 0 多余，杜绝英文回退影响体验。"),
    ("Grad-CAM 梯度修复", "识别 softmax 饱和导致梯度趋近 0，改为在分类头 linear 原始 logits 反传，热力图清晰稳定。"),
    ("权重自动部署", "训练结束自动将 best.pt 复制到服务端模型目录，模型即训即用，避免手动遗漏。"),
    ("轻量易部署", "全程软件实现，普通含 GPU 的电脑即可运行；一键 setup.bat / run.bat 启动，降低部署门槛。"),
]
pw2 = Inches(5.7)
ph2 = Inches(2.25)
pgx = Inches(0.25)
pgy = Inches(0.25)
for i, (t, d) in enumerate(points):
    col = i % 2
    row = i // 2
    x = Inches(0.9) + col * (pw2 + pgx)
    y = Inches(1.9) + row * (ph2 + pgy)
    card(s, x, y, pw2, ph2, line=LINE)
    rect(s, x, y, Inches(0.14), ph2, fill=SECONDARY)
    icon_circle(s, x + Inches(0.4), y + Inches(0.35), Inches(0.6), ["译", "证", "权", "轻"][i], fill=MINT_SOFT, size=15, tc=PRIMARY)
    txt(s, x + Inches(1.2), y + Inches(0.32), pw2 - Inches(1.5), Inches(0.6),
        [{"runs": [(t, {"size": 17, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    txt(s, x + Inches(1.2), y + Inches(0.95), pw2 - Inches(1.5), Inches(1.15),
        [{"runs": [(d, {"size": 12.5, "c": INK})]}], line_spacing=1.2)
footer(s, 11)

# ================= Slide 12 应用场景 =================
s = new_slide()
title_bar(s, "04", "应用场景：服务四类目标用户", "从个人到机构的价值覆盖")
scenes = [
    ("家庭园艺爱好者", "随手一拍识别阳台/庭院植物病害，获得通俗易懂的养护与防治建议。"),
    ("中小型种植户", "田间早发现、早防治，科学用药、降低损失与农残，提升收益。"),
    ("农技推广站", "作为基层辅助诊断工具，提升一线服务的专业性与响应效率。"),
    ("农资/植保企业", "辅助精准开方与用药推荐，推动减量增效与药肥科学配给。"),
]
scw = Inches(5.7)
sch = Inches(2.2)
for i, (t, d) in enumerate(scenes):
    col = i % 2
    row = i // 2
    x = Inches(0.9) + col * (scw + Inches(0.25))
    y = Inches(1.9) + row * (sch + Inches(0.25))
    card(s, x, y, scw, sch, line=LINE)
    icon_circle(s, x + Inches(0.4), y + Inches(0.4), Inches(0.85), ["家", "田", "站", "企"][i], fill=SECONDARY, size=20)
    txt(s, x + Inches(1.5), y + Inches(0.38), scw - Inches(1.8), Inches(0.6),
        [{"runs": [(t, {"size": 19, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    txt(s, x + Inches(1.5), y + Inches(1.05), scw - Inches(1.8), Inches(1.0),
        [{"runs": [(d, {"size": 13, "c": INK})]}], line_spacing=1.2)
footer(s, 12)

# ================= Slide 13 创新点 =================
s = new_slide()
title_bar(s, "05", "创新点：从「识别」到「闭环」的升级", "三大差异化优势")
innovs = [
    ("完整闭环", "从「仅识别什么病」升级为「识别 → 定位 → 评估 → 处方」一步到位，直接回答「怎么治」。"),
    ("双引擎融合", "深度学习视觉诊断与生成式大模型决策深度融合，诊断可解释、处方可落地。"),
    ("低成本规模化", "全程软件实现、轻量部署，普通电脑即可运行，成本低、易推广，适配基层场景。"),
]
iw = Inches(3.7)
ig = Inches(0.22)
iy = Inches(2.0)
for i, (t, d) in enumerate(innovs):
    x = Inches(0.9) + i * (iw + ig)
    card(s, x, iy, iw, Inches(3.6), fill=PRIMARY)
    icon_circle(s, x + Inches(1.55), iy + Inches(0.5), Inches(0.7), ["①", "②", "③"][i], fill=MINT, tc=PRIMARY_DARK, size=18)
    txt(s, x + Inches(0.4), iy + Inches(1.5), iw - Inches(0.8), Inches(0.7),
        [{"runs": [(t, {"size": 22, "bold": True, "c": "FFFFFF", "name": TITLE_FONT})]}], align=PP_ALIGN.CENTER)
    txt(s, x + Inches(0.45), iy + Inches(2.25), iw - Inches(0.9), Inches(1.2),
        [{"runs": [(d, {"size": 13, "c": "D9F2E0"})]}], align=PP_ALIGN.CENTER, line_spacing=1.25)
footer(s, 13)

# ================= Slide 14 应用价值 =================
s = new_slide()
title_bar(s, "05", "应用价值与社会意义", "科技赋能农业，助力乡村振兴")
txt(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(1.3),
    [{"runs": [("让专业植保知识，零门槛触达每一位种植者。", {"size": 24, "bold": True, "c": PRIMARY, "name": TITLE_FONT})]}])
vals = [
    ("早发现 · 早防治", "降低病虫害减产损失"),
    ("减肥 · 减药", "响应农药化肥减量增效"),
    ("数字乡村", "AI+ 智慧农业落地示范"),
]
vw2 = Inches(3.7)
for i, (t, d) in enumerate(vals):
    x = Inches(0.9) + i * (vw2 + Inches(0.22))
    card(s, x, Inches(3.8), vw2, Inches(2.2), line=LINE)
    rect(s, x + Inches(0.3), Inches(4.1), Inches(0.5), Inches(0.5), fill=MINT, radius=0.3, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    txt(s, x + Inches(0.3), Inches(4.7), vw2 - Inches(0.6), Inches(0.6),
        [{"runs": [(t, {"size": 17, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}])
    txt(s, x + Inches(0.3), Inches(5.25), vw2 - Inches(0.6), Inches(0.6),
        [{"runs": [(d, {"size": 12.5, "c": MUTED})]}], line_spacing=1.1)
footer(s, 14)

# ================= Slide 15 成果展示 =================
s = new_slide()
title_bar(s, "05", "成果概览", "已完成的系统能力与验证结果")
res = [
    ("识别引擎", "38 类识别（14 种作物），Top-1 99.7%"),
    ("定位可视化", "Grad-CAM 病灶热力图"),
    ("处方生成", "大模型个性化防治处方"),
    ("端到端验证", "/predict 闭环联调通过"),
]
rw = Inches(5.7)
rh = Inches(1.15)
for i, (t, d) in enumerate(res):
    col = i % 2
    row = i // 2
    x = Inches(0.9) + col * (rw + Inches(0.25))
    y = Inches(1.95) + row * (rh + Inches(0.25))
    card(s, x, y, rw, rh, line=LINE)
    icon_circle(s, x + Inches(0.35), y + Inches(0.32), Inches(0.55), "✓", fill=SECONDARY, size=15)
    txt(s, x + Inches(1.15), y + Inches(0.18), rw - Inches(1.4), Inches(0.5),
        [{"runs": [(t, {"size": 16, "bold": True, "c": PRIMARY_DARK})]}])
    txt(s, x + Inches(1.15), y + Inches(0.66), rw - Inches(1.4), Inches(0.4),
        [{"runs": [(d, {"size": 12, "c": MUTED})]}])
# 演示视频
rect(s, Inches(0.9), Inches(5.15), Inches(11.55), Inches(1.3), fill=PRIMARY_DARK, radius=0.1, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
icon_circle(s, Inches(1.25), Inches(5.5), Inches(0.6), "▶", fill=MINT, tc=PRIMARY_DARK, size=15)
txt(s, Inches(2.15), Inches(5.35), Inches(9.5), Inches(0.5),
    [{"runs": [("演示视频", {"size": 16, "bold": True, "c": "FFFFFF", "name": TITLE_FONT})]}])
txt(s, Inches(2.15), Inches(5.8), Inches(9.5), Inches(0.5),
    [{"runs": [("1080p · 中文配音 · 完整演示「上传 → 识别 → 定位 → 处方」运行效果", {"size": 12, "c": "BFE6CF"})]}])
footer(s, 15)

# ================= Slide 16 团队介绍 =================
s = new_slide()
title_bar(s, "06", "团队介绍", "禾目团队 · 三位成员协同分工")
members = [
    ("魏尊浩", "队长 · 算法与全栈", ["系统架构设计", "YOLO 模型训练与调优", "后端接口与闭环集成"]),
    ("徐佳静", "前端与产品", ["前端页面与交互设计", "产品需求与体验打磨", "演示物料与视觉"]),
    ("王韬淦", "数据与测试", ["数据集整理与校验", "处方引擎接口联调", "测试与使用文档"]),
]
mw = Inches(3.7)
mg = Inches(0.22)
for i, (name, role, items) in enumerate(members):
    x = Inches(0.9) + i * (mw + mg)
    card(s, x, Inches(2.0), mw, Inches(4.2), line=LINE)
    icon_circle(s, x + Inches(1.43), Inches(2.35), Inches(0.95), name[0], fill=SECONDARY, size=26)
    txt(s, x + Inches(0.3), Inches(3.5), mw - Inches(0.6), Inches(0.6),
        [{"runs": [(name, {"size": 20, "bold": True, "c": PRIMARY_DARK, "name": TITLE_FONT})]}], align=PP_ALIGN.CENTER)
    txt(s, x + Inches(0.3), Inches(4.05), mw - Inches(0.6), Inches(0.5),
        [{"runs": [(role, {"size": 13, "bold": True, "c": SECONDARY})]}], align=PP_ALIGN.CENTER)
    lines = "".join([f"• {it}\n" for it in items]).rstrip()
    txt(s, x + Inches(0.55), Inches(4.55), mw - Inches(1.0), Inches(1.5),
        [{"runs": [(lines, {"size": 12.5, "c": INK})]}], line_spacing=1.35)
footer(s, 16)

# ================= Slide 17 结语 =================
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, SW, SH, fill=PRIMARY_DARK)
rect(s, Inches(5.4), Inches(2.4), Inches(2.5), Inches(2.5), fill="1D5A38", shape=MSO_SHAPE.OVAL)
pic(s, ASSET / "logo_512x512.png", Inches(5.9), Inches(2.9), w=Inches(1.5))
txt(s, Inches(1.0), Inches(4.9), Inches(11.33), Inches(0.9),
    [{"runs": [("科技赋能农业，让每一株作物都被看见。", {"size": 30, "bold": True, "c": "FFFFFF", "name": TITLE_FONT})]}], align=PP_ALIGN.CENTER)
txt(s, Inches(1.0), Inches(5.9), Inches(11.33), Inches(0.6),
    [{"runs": [("感谢观看 · 敬请指正", {"size": 15, "c": MINT})]}], align=PP_ALIGN.CENTER)
chip(s, Inches(11.0), Inches(6.6), Inches(1.75), Inches(0.44), "AI 辅助制作", fill="1D5A38", tc="BFE6CF", size=11)

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides._sldIdLst))