"""把 frontend/_demo_leaf.jpg 的背景替换成纯白色，使其通过「叶片 + 纯色背景」校验。

用法：
  .venv/Scripts/python.exe scripts/make_demo_compliant.py

输出：frontend/_demo_leaf_compliant.jpg
"""
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "_demo_leaf.jpg"
DST = ROOT / "frontend" / "_demo_leaf_compliant.jpg"


def segment_leaf(img_bgr: np.ndarray) -> np.ndarray:
    """用颜色 + 形态学分割叶片前景，返回单通道掩膜。"""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # 绿色通道（叶片主体，含黄绿）
    green = cv2.inRange(hsv, (25, 40, 40), (100, 255, 255))
    # 褐色/枯黄通道（病斑、枯边）
    brown = cv2.inRange(hsv, (0, 30, 20), (25, 255, 180))
    # 排除过暗阴影
    dark = cv2.inRange(hsv, (0, 0, 0), (180, 255, 35))

    fg = cv2.bitwise_or(green, brown)
    fg = cv2.bitwise_and(fg, cv2.bitwise_not(dark))

    # 形态学：先闭运算补洞，再开运算去噪
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=2)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=1)

    # 只保留最大连通区域（避免小噪点）
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    if num_labels > 1:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = (labels == largest).astype(np.uint8) * 255

    return fg


def main():
    img = cv2.imread(str(SRC))
    if img is None:
        raise SystemExit(f"无法读取 {SRC}")

    mask = segment_leaf(img)

    # 背景替换为纯白，前景保留原图
    white_bg = np.full_like(img, 255)
    fg = cv2.bitwise_and(img, img, mask=mask)
    bg = cv2.bitwise_and(white_bg, white_bg, mask=cv2.bitwise_not(mask))
    out = cv2.add(fg, bg)

    # 轻微高斯模糊边缘，减少锯齿感
    mask_3 = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
    out = (out * mask_3 + white_bg * (1 - mask_3)).astype(np.uint8)

    cv2.imwrite(str(DST), out)
    print(f"已生成合规示例图：{DST}")


if __name__ == "__main__":
    main()
