"""使用 YOLO11n 分类模型在 PlantVillage 上训练病害识别模型。

用法：
  python scripts/train.py --data data/plantvillage --epochs 30 --imgsz 224 --device 0

训练进度会实时写入项目根 status.json，供进度面板（serve_panel.bat）展示。
"""
import argparse
from pathlib import Path

from ultralytics import YOLO

import status as st

ROOT = Path(__file__).resolve().parent.parent
MODEL_WORKING = ROOT / "models" / "yolo11n-cls.pt"


def _on_epoch_end(trainer) -> None:
    epoch = int(getattr(trainer, "epoch", 0)) + 1
    epochs = int(getattr(trainer, "epochs", 30))
    m = getattr(trainer, "metrics", {}) or {}
    top1 = m.get("metrics/accuracy_top1")
    loss = m.get("train/loss")
    st.update_train(
        epoch=epoch,
        epochs=epochs,
        top1=round(float(top1), 4) if top1 is not None else None,
        loss=round(float(loss), 4) if loss is not None else None,
    )


def main(data: str, epochs: int, imgsz: int, batch: int, device: str) -> None:
    data_path = Path(data)
    if not data_path.is_absolute():
        data_path = ROOT / data_path
    model_file = MODEL_WORKING if MODEL_WORKING.exists() else "yolo11n-cls.pt"
    print(f"[train] data={data_path}")
    print(f"[train] model={model_file}  epochs={epochs}  imgsz={imgsz}  device={device}")

    model = YOLO(str(model_file))
    if hasattr(model, "add_callback"):
        model.add_callback("on_train_epoch_end", _on_epoch_end)

    st.update_train(active=True, label="训练 YOLO11n 分类模型", epoch=0, epochs=epochs, top1=None, loss=None)
    model.train(
        data=str(data_path),
        epochs=epochs,
        imgsz=imgsz,
        device=device,
        batch=batch,
        project=str(ROOT / "runs"),
        name="agriguard",
        exist_ok=True,
    )
    st.update_train(active=False, label="训练完成", epoch=epochs, epochs=epochs)
    print("训练完成，best.pt 位于 runs/agriguard/weights/best.pt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/plantvillage")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()
    main(args.data, args.epochs, args.imgsz, args.batch, args.device)