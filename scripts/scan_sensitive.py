"""敏感信息扫描：参赛材料提交前的合规自查。

【为什么需要】
iCAN 创新赛道采用双盲评审，材料中出现院校名称、参赛单位名称、指导老师姓名等
**每处扣 5 分**；且本项目的开发日志、交接文档、训练参数文件恰是
「开发过程可追溯」举证时最容易被一并带出的材料——历史上就查出过 8 处
真实用户名与本地路径。人工肉眼检查不可靠，故做成脚本。

【用法】
    .venv\\Scripts\\python.exe scripts\\scan_sensitive.py            # 扫描项目内文本文件
    .venv\\Scripts\\python.exe scripts\\scan_sensitive.py <路径>     # 扫描指定文件/目录
                                                                   # （导出物也可以直接扫）

退出码：0 = 未发现疑似问题；1 = 发现需人工确认的命中项。

【注意】
- 这是**辅助**工具，命中不等于违规（例如代码里讨论"不要写学校名"也会命中）。
  请逐条人工确认，不要直接当成结论。
- 二进制与数据目录会被跳过。图片/视频里的文字扫描需要 OCR，本脚本不覆盖——
  导出物请连同**PPT 备注页、视频字幕、海报小字**一并人工复核。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 本脚本自身包含规则模式（如「职业技术学院」），会被自己命中，故跳过自身
SELF = Path(__file__).resolve()

# 扫描范围：只扫文本类文件，跳过数据/环境/依赖目录
SKIP_DIRS = {
    ".venv", "venv", "data", "uploads", "node_modules", "__pycache__",
    ".git", ".pytest_cache", "runs", "models", "assets",
    "backup",  # 清理前备份目录，非提交内容
}
TEXT_EXT = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".html", ".htm", ".css",
    ".js", ".ts", ".bat", ".cmd", ".ps1", ".sh", ".ini", ".cfg", ".toml",
    ".csv", ".env", ".example", ".gitignore", "",
}
MAX_BYTES = 2 * 1024 * 1024  # 超过 2MB 的文本不扫（避免扫到大日志）

# ---------------------------------------------------------------------------
# 规则：(类别, 正则, 严重度, 说明)
# 严重度 P0 = 直接构成身份泄露；P1 = 需人工确认
# ---------------------------------------------------------------------------
RULES = [
    ("院校名称", r"[\u4e00-\u9fa5]{2,10}(大学|学院|职业技术学院|高等专科学校)", "P0",
     "出现疑似院校名称，双盲材料中每处扣 5 分"),
    ("导师称谓", r"(指导教师|指导老师|导师|带队老师)[：:]\s*[\u4e00-\u9fa5]{2,4}", "P0",
     "出现疑似指导教师姓名"),
    ("导师称谓(无姓名)", r"(指导教师|指导老师)[：:]\s*(无|None|—|-|未填)", "P1",
     "「指导教师：无」属合规声明，但**对外材料**中建议删除该行，避免被误读为信息缺失"),
    ("本地用户名路径", r"[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._-]+", "P0",
     "出现 Windows 用户目录路径，用户名可能是真实姓名拼音，可被反查身份"),
    ("本地用户目录(正斜杠)", r"[A-Za-z]:/Users/[A-Za-z0-9._-]+", "P0",
     "同上（正斜杠写法）"),
    ("疑似学号/工号", r"(学号|工号|账号)[：:]\s*[0-9]{4,}", "P0",
     "出现疑似学号或工号"),
    ("身份证号", r"\b[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b", "P0",
     "出现疑似身份证号"),
    ("手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)", "P1",
     "出现疑似手机号，需确认是否为公开联系方式"),
    ("邮箱", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "P1",
     "出现邮箱，需确认是否可公开"),
    ("示例占位邮箱", r"[\w.-]+@example\.(com|org|edu|invalid)", "P1",
     "占位邮箱（如本仓库自建素材的署名占位），对外材料中建议替换或删除"),
]

COMPILED = [(name, re.compile(pat), sev, desc) for name, pat, sev, desc in RULES]


def iter_files(targets):
    for t in targets:
        p = Path(t)
        if p.is_file():
            yield p
            continue
        if not p.is_dir():
            print(f"[跳过] 路径不存在: {p}")
            continue
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if f.resolve() == SELF:
                continue
            if any(part in SKIP_DIRS for part in f.parts):
                continue
            if f.suffix.lower() not in TEXT_EXT:
                continue
            try:
                if f.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield f


def main() -> int:
    targets = sys.argv[1:] or [str(ROOT)]
    hits = []
    scanned = 0

    for f in iter_files(targets):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            for name, rx, sev, desc in COMPILED:
                for m in rx.finditer(line):
                    hits.append({
                        "file": str(f),
                        "line": lineno,
                        "kind": name,
                        "sev": sev,
                        "text": m.group(0)[:80],
                        "desc": desc,
                    })

    print(f"扫描文件数: {scanned}")
    print(f"命中条数:   {len(hits)}")
    print()

    if not hits:
        print("未发现疑似敏感信息。")
        print("提醒：图片/视频中的文字（PPT 备注页、视频字幕、海报小字）本脚本不覆盖，请人工复核。")
        return 0

    p0 = [h for h in hits if h["sev"] == "P0"]
    p1 = [h for h in hits if h["sev"] != "P0"]

    if p0:
        print("=" * 72)
        print(f"P0 —— 直接构成身份泄露风险，共 {len(p0)} 处，提交前必须处理")
        print("=" * 72)
        for h in p0:
            rel = h["file"].replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "")
            print(f"  [{h['kind']}] {rel}:{h['line']}")
            print(f"      命中内容: {h['text']}")
            print(f"      说明: {h['desc']}")
        print()

    if p1:
        print("=" * 72)
        print(f"P1 —— 需人工确认，共 {len(p1)} 处")
        print("=" * 72)
        for h in p1:
            rel = h["file"].replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", "")
            print(f"  [{h['kind']}] {rel}:{h['line']}  ->  {h['text']}")

    print()
    print("提示：命中不等于违规（例如规则文档里讨论「不要写学校名」也会命中）。请逐条确认。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
