"""生成 PPT 附加高清素材：封面背景图 + 病叶/健康叶对比样张（圆角）。"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSET = ROOT / "参赛材料" / "assets"
GEN = ROOT / "media" / "gen"
ASSET.mkdir(parents=True, exist_ok=True)

TOP = (18, 58, 38)      # #123A26 深绿
BOT = (16, 72, 44)      # 底部略亮


def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0], im.size[1]), radius, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im.convert("RGBA"), (0, 0), mask)
    return out


def cover_bg():
    ph = Image.open(GEN / "leaf_disease_hi.jpg").convert("RGB")
    w, h = ph.size
    target = 16 / 9
    ca = w / h
    if ca > target:
        nw = int(h * target)
        ph = ph.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        ph = ph.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    ph = ph.resize((2560, 1440), Image.LANCZOS)

    # 左暗右亮的横向渐变遮罩，保证左侧标题文字清晰、右侧保留病叶质感
    W, H = ph.size
    gx = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]  # (1,W,1)
    # 左 0 -> 右 1
    dark_frac = 0.78 - 0.30 * gx      # 左侧 0.78 暗化，右侧 0.48 暗化
    arr = np.asarray(ph, dtype=np.float32)
    base = np.array(TOP, dtype=np.float32)[None, None, :] * (1 - gx) + \
           np.array(BOT, dtype=np.float32)[None, None, :] * gx
    out = arr * (1 - dark_frac) + base * dark_frac
    Image.fromarray(out.astype(np.uint8), "RGB").save(ASSET / "cover_bg.jpg", quality=95, subsampling=0)
    print("cover_bg done")


def sample_cards():
    for name, src in [("sample_disease", GEN / "leaf_disease_hi.jpg"),
                      ("sample_healthy", GEN / "leaf_healthy_hi.jpg")]:
        im = Image.open(src).convert("RGB").resize((1000, 1000), Image.LANCZOS)
        rounded(im, 40).save(ASSET / f"{name}.png")
        print(name, "done")


if __name__ == "__main__":
    cover_bg()
    sample_cards()