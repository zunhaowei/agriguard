"""端到端冒烟测试：真实病叶图 -> 识别 -> 中文映射 -> 处方。

用法（在项目根目录执行）：
    .venv\\Scripts\\python.exe scripts\\smoke_test.py

【本次审查修正】原实现直接对 `detect()` 的返回值做迭代：
    detections = det.detect(path)
    for d in detections: ...
但 `detect()` 返回的是四元组 `(detections, ood_score, is_ood, is_warning)`，
迭代它得到的是"列表本身 + 三个布尔/浮点"，随后 `d.name` 必然抛
AttributeError。该脚本因此一直是坏的（只是没人跑）。现改为正确解包。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.detector import Detector  # noqa: E402
from app.prescriber import Prescriber  # noqa: E402

VAL_ROOT = ROOT / "data" / "plantvillage" / "val"


def main() -> int:
    if not VAL_ROOT.exists():
        print(f"[跳过] 未找到验证集目录：{VAL_ROOT}")
        print("       数据集未随仓库分发，需先运行 scripts/organize_plantvillage.py 整理。")
        return 1

    imgs = [p for p in sorted(VAL_ROOT.rglob("*.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    if not imgs:
        print(f"[跳过] 验证集目录为空：{VAL_ROOT}")
        return 1

    sample = next((p for p in imgs if "healthy" not in str(p)), imgs[0])
    print(f"样本文件: {sample.name}")
    print(f"真实类别: {sample.parent.name}")

    detector = Detector()
    detections, ood_score, is_ood, is_warning = detector.detect(str(sample))

    print(f"\nOOD 分布相似度: {ood_score}  (拒识={is_ood}, 警告={is_warning})")
    print(f"模型信息: {detector.model_info()}")

    print("\nTop3 识别:")
    for d in detections:
        print(f"  {d.name}  ({d.confidence:.4f})")

    if not detections:
        print("[失败] 未返回任何识别结果。")
        return 1

    prescription, source = Prescriber().generate(detections)
    print(f"\n处方（来源={source}）:")
    if prescription is None:
        print("  未生成处方。")
        return 1
    for field in ("disease", "severity", "summary", "biological", "chemical", "tips"):
        print(f"  {field}: {getattr(prescription, field)}")

    print("\n冒烟测试通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
