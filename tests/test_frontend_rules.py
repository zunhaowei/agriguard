"""前端静态合规 + AC-15 可执行验证（团队级 P0 视觉/交互纪律的回归护栏）。

为什么要有这一层：团队级 P0 规则（禁止 emoji 当功能图标、禁止紫→粉渐变、
禁止弹跳缓动、禁止 :root Token 之外硬编码颜色）以及 XSS 防护、AC-15 语音降级，
原先都靠「人工审查 + 口头约定」。人工检查会漏、会漂移。这里把它们固化为
可重跑的断言，任何人改前端改坏了都会被 CI 拦下来。

覆盖：
1. 禁止 emoji 作为功能图标（P0）
2. 禁止 :root Token 之外硬编码颜色（#fff/#000 及其 6 位写法等灰度白/黑除外）
3. 禁止弹跳缓动 cubic-bezier(0.68, -0.55, 0.265, 1.55)
4. 禁止紫→粉渐变
5. 对话框必须 role="dialog" + aria-modal
6. XSS 回归：layout.js 的 el() 用 textContent/createTextNode；innerHTML 不得拼接数据
7. AC-15：浏览器不支持语音合成时，必须「可见降级提示 + 朗读按钮 disabled」——
   用 Node 在极简 DOM shim 里**真实执行** frontend/layout.js + app.js 来验证
   （见 tests/ac15_tts_probe.js）。真实音频是否发声属无头环境无法验证项，仍不做断言。
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

HTML_FILES = sorted(FRONTEND.glob("*.html"))
JS_FILES = sorted(FRONTEND.glob("*.js"))
CSS_FILES = sorted(FRONTEND.glob("*.css"))

# --- emoji（团队级 P0：功能图标一律描边 SVG，禁用 emoji）---
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F9FF"   # 各类 emoji / 图形符号
    "\U00002600-\U000026FF"    # 杂项符号
    "\U00002700-\U000027BF]"   # 装饰符号（含 ✅ 等）
)

# --- 硬编码颜色：仅检查「真正落到 UI 上」的位置 ---
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# 允许出现的灰度白/黑（Token 之外的排版兜底色）；其余一律必须走 :root 变量
ALLOWED_HEX = {"#fff", "#ffffff", "#000", "#000000"}
# JS 里只有「样式赋值」算硬编码颜色；console.log 的调试着色字符串不算 UI 颜色
JS_STYLE_ASSIGN_RE = re.compile(r"\.style\.(?:cssText|[A-Za-z]+)\s*=\s*([\"'])(.*?)\1")
JS_SETPROP_RE = re.compile(r"\.style\.setProperty\s*\(\s*[\"'][^\"']*[\"']\s*,\s*([\"'])(.*?)\1")
HTML_INLINE_STYLE_RE = re.compile(r"style\s*=\s*([\"'])(.*?)\1")

BOUNCE_RE = re.compile(
    r"cubic-bezier\(\s*0?\.68\s*,\s*-0?\.55\s*,\s*0?\.265\s*,\s*1\.55\s*\)"
)
PURPLE_HEX = {"#7c3aed", "#a855f7", "#9333ea", "#8b5cf6", "#c026d3"}
PINK_HEX = {"#ec4899", "#db2777", "#f472b6", "#ff69b4"}


def _read(p):
    return Path(p).read_text(encoding="utf-8")


def _strip_root_block(css):
    """去掉 styles.css 里第一个 :root { ... } 代码块，返回 (剩余文本, 该块文本)。"""
    m = re.search(r":root\s*\{", css)
    if not m:
        return css, ""
    start = m.start()
    i = css.index("{", m.start())
    depth = 0
    for j in range(i, len(css)):
        if css[j] == "{":
            depth += 1
        elif css[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                return css[:start] + css[end:], css[start:end]
    return css[:start], css[start:]


def _function_src(src, name):
    """按大括号配对抽取 `function <name>(...) { ... }` 的完整源码。"""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", src)
    assert m, f"未找到函数 {name}()"
    i = src.index("{", m.end())
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise AssertionError(f"函数 {name}() 大括号不配对")


# ---------------------------------------------------------------------------
# 1. 禁止 emoji 作为功能图标（P0）
# ---------------------------------------------------------------------------
def test_no_emoji_as_functional_icons():
    offenders = []
    for f in HTML_FILES + JS_FILES:
        for hit in EMOJI_RE.findall(_read(f)):
            offenders.append(f"{f.name}: {hit!r}")
    assert not offenders, (
        "检测到 emoji 作为 UI 图标（团队级 P0 缺陷），请替换为项目锁定图标库的语义图标：\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# 2. 禁止 :root Token 之外的硬编码颜色
# ---------------------------------------------------------------------------
def test_no_hardcoded_colors_outside_root_tokens():
    offenders = []

    for f in CSS_FILES:
        rest, root_block = _strip_root_block(_read(f))
        assert root_block, f"{f.name} 中未找到 :root Token 块（设计令牌应集中于此）"
        for h in HEX_RE.findall(rest):
            if h.lower() not in ALLOWED_HEX:
                offenders.append(f"{f.name}: {h}")

    for f in HTML_FILES:
        for _, val in HTML_INLINE_STYLE_RE.findall(_read(f)):
            for h in HEX_RE.findall(val):
                if h.lower() not in ALLOWED_HEX:
                    offenders.append(f"{f.name} inline-style: {h}")

    for f in JS_FILES:
        src = _read(f)
        for _, val in JS_STYLE_ASSIGN_RE.findall(src) + JS_SETPROP_RE.findall(src):
            for h in HEX_RE.findall(val):
                if h.lower() not in ALLOWED_HEX:
                    offenders.append(f"{f.name} style-assign: {h}")

    assert not offenders, (
        "检测到 :root Token 之外的硬编码颜色，请改用 CSS 变量：\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# 3. 禁止弹跳缓动
# ---------------------------------------------------------------------------
def test_no_bounce_easing():
    offenders = [f.name for f in CSS_FILES + JS_FILES + HTML_FILES if BOUNCE_RE.search(_read(f))]
    assert not offenders, f"检测到弹跳缓动 cubic-bezier(0.68,-0.55,0.265,1.55)：{offenders}"


# ---------------------------------------------------------------------------
# 4. 禁止紫→粉渐变
# ---------------------------------------------------------------------------
def test_no_purple_pink_gradient():
    offenders = []
    for f in CSS_FILES + JS_FILES + HTML_FILES:
        text = _read(f)
        low = text.lower()
        if "purple" in low or "pink" in low:
            offenders.append(f"{f.name}: 出现 purple/pink 关键字")
        for grad in re.findall(r"gradient\([^)]*\)", low):
            hexes = {h for h in HEX_RE.findall(grad)}
            if (hexes & PURPLE_HEX) and (hexes & PINK_HEX):
                offenders.append(f"{f.name}: 渐变含紫→粉色值 {sorted(hexes)}")
    assert not offenders, "检测到紫色→粉色渐变（团队级禁用）：\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# 5. 对话框可访问性：role="dialog" + aria-modal
# ---------------------------------------------------------------------------
def test_dialog_has_role_and_aria_modal():
    text = "".join(_read(f) for f in JS_FILES + HTML_FILES)
    assert re.search(r'setAttribute\(\s*"role"\s*,\s*"dialog"\s*\)|role="dialog"', text), (
        "未找到 role=\"dialog\"，对话框缺少可访问性角色"
    )
    assert "aria-modal" in text, "对话框缺少 aria-modal"
    assert "aria-labelledby" in text, "对话框缺少 aria-labelledby（标题关联）"


# ---------------------------------------------------------------------------
# 6. XSS 回归：el() 用 textContent；innerHTML 不得拼接数据
# ---------------------------------------------------------------------------
def test_el_helper_uses_textcontent_not_innerhtml():
    src = _read(FRONTEND / "layout.js")
    body = _function_src(src, "el")
    assert "textContent" in body or "createTextNode" in body, (
        "layout.js 的 el() 未使用 textContent/createTextNode —— 用户数据可能被当 HTML 注入"
    )
    assert "innerHTML" not in body, "layout.js 的 el() 出现 innerHTML，存在存储型 XSS 风险"


def test_innerhtml_assignments_are_static_only():
    """所有 innerHTML 赋值只允许「静态 SVG 图标 / 字面量 / 已存的静态片段」，禁止拼接。"""
    allowed_rhs = re.compile(
        r"^(?:AGRI\.)?iconSvg\("      # 静态描边图标表
        r"|^[A-Za-z_$][\w$]*$"        # 来自 data-idle-html 等已存的静态片段
        r"|^'[^']*'$"                 # 单引号字面量（内部可含双引号）
        r"|^\"[^\"]*\"$"              # 双引号字面量
    )
    offenders = []
    for f in JS_FILES:
        for rhs in re.findall(r"\w+(?:\.\w+)?\.innerHTML\s*=\s*([^;]*);", _read(f)):
            rhs = rhs.strip()
            if "+" in rhs:
                offenders.append(f"{f.name}: innerHTML 拼接了字符串 → {rhs[:80]}")
            elif not allowed_rhs.match(rhs):
                offenders.append(f"{f.name}: innerHTML 赋值不在白名单 → {rhs[:80]}")
    assert not offenders, (
        "检测到可能把数据拼进 innerHTML 的写法（存储型 XSS 风险）：\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# 7. AC-15（可执行）：不支持语音合成 → 可见降级提示 + 按钮 disabled
# ---------------------------------------------------------------------------
NODE = shutil.which("node")
PROBE = Path(__file__).resolve().parent / "ac15_tts_probe.js"
requires_node = pytest.mark.skipif(
    NODE is None, reason="需要本机安装 Node 才能执行前端 JS 做 AC-15 降级验证"
)


def _run_probe(scenario):
    proc = subprocess.run(
        [NODE, str(PROBE), scenario, str(ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"AC-15 探针执行失败 rc={proc.returncode}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@requires_node
def test_ac15_tts_unsupported_shows_visible_degrade():
    """window.speechSynthesis 缺失时：按钮必须 disabled，且出现可见降级提示（非静默）。"""
    res = _run_probe("unsupported")
    assert res["errors"] == [], f"前端脚本在降级场景下抛错：{res['errors']}"
    assert res["speechSupported"] is False
    assert res["ttsDisabled"] is True, "不支持语音合成时，朗读按钮必须 disabled（不能是静默可点）"
    assert res["hasUnsupportedMsg"] is True, (
        f"未看到可见的降级提示；实际 body 文本={res['bodyText']!r}"
    )
    assert res["ttsAriaLabel"] == "当前浏览器不支持语音朗读", (
        f"按钮 aria-label 未如实描述降级原因：{res['ttsAriaLabel']!r}"
    )


@requires_node
def test_ac15_tts_supported_baseline():
    """支持语音合成时：按钮可用、且**不**误报降级提示（反向护栏，防过度降级）。"""
    res = _run_probe("supported")
    assert res["errors"] == [], f"前端脚本在支持场景下抛错：{res['errors']}"
    assert res["speechSupported"] is True
    assert res["ttsDisabled"] is False, "支持语音合成时按钮不应被禁用"
    assert res["hasUnsupportedMsg"] is False, "支持语音合成时不应出现「不支持」提示"
