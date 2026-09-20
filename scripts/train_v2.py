"""增强版训练脚本：更大模型 + 高分辨率 + 强数据增强 + 类别平衡。

用法示例（RTX 4050 / CUDA 可用）：
  python scripts/train_v2.py --data data/plantvillage --epochs 50 --imgsz 448 --model-size s --strong-aug --balance --device 0

说明：
- --model-size 可选 n/s/m/l/x，s/m/l/x 比 nano 容量更大，细粒度病害区分能力更强。
- --imgsz 默认 448，保留更多病斑纹理细节。
- --strong-aug 开启旋转、缩放、颜色抖动、擦除等增强，提升泛化。
- --balance 对训练集少数类过采样，缓解类别不平衡。
- 训练完成后 best.pt 位于 runs/agriguard_v2/weights/best.pt，可覆盖 models/best.pt。
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

import status as st

ROOT = Path(__file__).resolve().parent.parent

PRETRAINED = {
    "n": "yolo11n-cls.pt",
    "s": "yolo11s-cls.pt",
    "m": "yolo11m-cls.pt",
    "l": "yolo11l-cls.pt",
    "x": "yolo11x-cls.pt",
}

# 强增强参数：适度但有效，专门针对病斑纹理的旋转、缩放、颜色变化
STRONG_AUG = dict(
    hsv_h=0.02,
    hsv_s=0.6,
    hsv_v=0.4,
    degrees=15,
    translate=0.1,
    scale=0.4,
    shear=5,
    perspective=0.0001,
    flipud=0.5,
    fliplr=0.5,
    mosaic=0.0,      # 分类任务通常关闭 mosaic
    mixup=0.0,
    copy_paste=0.0,
    erasing=0.3,
    auto_augment="randaugment",
)


def _on_epoch_end(trainer):
    epoch = int(getattr(trainer, "epoch", 0)) + 1
    epochs = int(getattr(trainer, "epochs", 50))
    m = getattr(trainer, "metrics", {}) or {}
    top1 = m.get("metrics/accuracy_top1")
    loss = m.get("train/loss")
    st.update_train(
        epoch=epoch,
        epochs=epochs,
        top1=round(float(top1), 4) if top1 is not None else None,
        loss=round(float(loss), 4) if loss is not None else None,
    )


def _balance_dataset(src: Path, dst: Path):
    """过采样少数类，使训练集每类样本数达到中位数。

    把数据整理为 data/plantvillage_balanced/train/<class>/，供 ultralytics 直接训练。
    """
    dst.mkdir(parents=True, exist_ok=True)
    class_dirs = [d for d in src.iterdir() if d.is_dir()]
    if not class_dirs:
        raise SystemExit(f"未在 {src} 下找到类别文件夹，无法做类别平衡。")

    counts = {d.name: len(list(d.glob("*"))) for d in class_dirs}
    target = int(sorted(counts.values())[len(counts) // 2])
    total_after = 0
    for d in class_dirs:
        imgs = list(d.glob("*"))
        n = len(imgs)
        out_dir = dst / d.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in imgs:
            shutil.copy2(f, out_dir / f.name)
        if n < target:
            extra = target - n
            for i in range(extra):
                src_f = imgs[i % n]
                dst_f = out_dir / f"{src_f.stem}_copy{i // n + 1}{src_f.suffix}"
                shutil.copy2(src_f, dst_f)
        total_after += max(n, target)
    print(f"[balance] 原训练集 {sum(counts.values())} 张，平衡后 {total_after} 张（每类约 {target} 张）。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/plantvillage")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=448)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--device", default="0")
    parser.add_argument("--model-size", choices=["n", "s", "m", "l", "x"], default="s",
                        help="YOLO11-cls 模型大小，s/m/l/x 容量更大、细粒度更强")
    parser.add_argument("--strong-aug", action="store_true",
                        help="启用强数据增强（旋转/缩放/颜色抖动/擦除/randaugment）")
    parser.add_argument("--balance", action="store_true",
                        help="对训练集少数类过采样，缓解类别不平衡")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = ROOT / data_path

    # 类别平衡：生成临时目录，不污染原数据
    if args.balance:
        balanced_root = ROOT / "data" / "plantvillage_balanced"
        _balance_dataset(data_path / "train", balanced_root / "train")
        if (data_path / "val").exists():
            shutil.copytree(data_path / "val", balanced_root / "val", dirs_exist_ok=True)
        data_path = balanced_root

    # 选择模型权重（本地优先，否则让 ultralytics 自动下载）
    model_file = PRETRAINED[args.model_size]
    local_weight = ROOT / "models" / model_file
    if local_weight.exists():
        model_file = str(local_weight)

    print(f"[train_v2] model={model_file} size={args.model_size}")
    print(f"[train_v2] data={data_path} epochs={args.epochs} imgsz={args.imgsz} batch={args.batch} device={args.device}")
    print(f"[train_v2] strong_aug={args.strong_aug} balance={args.balance}")

    model = YOLO(model_file)
    if hasattr(model, "add_callback"):
        model.add_callback("on_train_epoch_end", _on_epoch_end)

    st.update_train(
        active=True,
        label=f"训练 YOLO11{args.model_size}-cls 增强模型",
        epoch=0,
        epochs=args.epochs,
        top1=None,
        loss=None,
    )

    train_kwargs = dict(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        device=args.device,
        batch=args.batch,
        project=str(ROOT / "runs"),
        name="agriguard_v2",
        exist_ok=True,
        seed=args.seed,
        deterministic=False,
        optimizer="SGD",  # 固定 SGD：auto 会选择 MuSGD，与 torch 2.13 有 view 兼容性 bug
    )
    if args.strong_aug:
        train_kwargs.update(STRONG_AUG)

    model.train(**train_kwargs)
    st.update_train(active=False, label="训练完成", epoch=args.epochs, epochs=args.epochs)
    print("训练完成，best.pt 位于 runs/agriguard_v2/weights/best.pt")
    print("建议：将 runs/agriguard_v2/weights/best.pt 复制到 models/best.pt 覆盖旧模型")


if __name__ == "__main__":
    main()
