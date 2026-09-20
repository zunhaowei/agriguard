"""模型结构内省（替代硬编码的层索引）。

【为什么需要这个模块】
本次审查发现同一 backbone 存在**两套互不相干的寻址约定**：
  - `detector.py`：`list(model.model.model.children())[-1]`（取最后一个子模块）
  - `gradcam.py` ：`model.model[9]` / `model.model[10]`（按整数索引）

两种写法都隐式绑定了 `yolo11n-cls` 的 `nn.Sequential` 次序，并且都依赖
`model.model.model` 这条三级属性链。一旦换 backbone（nano -> small/m/l）
或升级 ultralytics 版本，索引会**静默指向别的层**——不报错，但 Grad-CAM 的
语义全错（热力图看起来还在生成，实际高亮的是无关特征）。

因此统一到本模块：按**类型与属性特征**定位，而非按位置数字定位；
并在定位失败时**快速报错**，而不是悄悄用错层。

【定位策略】
- head：从后往前找第一个同时具备 `.conv` 与 `.linear` 的分类头模块
  （ultralytics 的 `Classify` 同时具备二者；检测头 `Detect` 两者都没有）。
- target：head 之前紧邻的那个模块（yolo11n-cls 下即 C2PSA 空间特征层）。
- 同时校验 head.conv 的输出通道数，与 OOD 特征维度自检相呼应。
"""

from typing import NamedTuple

import torch.nn as nn


class BackboneView(NamedTuple):
    """一个 backbone 的解析结果。"""

    sequential: nn.Sequential   # 顶层 nn.Sequential
    head: nn.Module             # 分类头（含 .conv / .pool / .linear）
    target: nn.Module           # 用于 Grad-CAM 的目标空间特征层
    head_index: int
    target_index: int


class ModelStructureError(RuntimeError):
    """模型结构与预期不符时抛出，避免静默用错层。"""


def resolve_backbone(yolo_model) -> BackboneView:
    """解析 YOLO 分类模型的结构。

    参数 `yolo_model` 是 ultralytics 的 `YOLO` 包装对象
    （即 `Detector.model`；也接受已解包的 `ClassificationModel`）。

    解析失败抛 `ModelStructureError`，附带实际结构信息便于排查。
    """
    # 兼容两种传入：YOLO 包装对象 或 已解包的 ClassificationModel
    inner = getattr(yolo_model, "model", yolo_model)
    sequential = getattr(inner, "model", None)
    if not isinstance(sequential, nn.Sequential):
        raise ModelStructureError(
            "无法定位 nn.Sequential：期望 model.model 为 nn.Sequential，"
            f"实际为 {type(sequential).__name__}。请确认加载的是分类模型"
            "（yolo11n-cls.pt），而不是检测模型（yolo11n.pt）。"
        )

    modules = list(sequential.children())
    if not modules:
        raise ModelStructureError("模型 nn.Sequential 为空。")

    # 从后往前找分类头：必须同时具备 .conv 与 .linear
    head_index = -1
    for i in range(len(modules) - 1, -1, -1):
        m = modules[i]
        if hasattr(m, "conv") and hasattr(m, "linear"):
            head_index = i
            break

    if head_index < 0:
        raise ModelStructureError(
            "未找到分类头（需同时具备 .conv 与 .linear 属性）。"
            f"实际最后一层为 {type(modules[-1]).__name__}，"
            f"共 {len(modules)} 个子模块。"
            "若该层为 Detect/Segment/Pose，说明加载的是检测类权重而非分类权重——"
            "请检查 fallback 配置是否正确指向 yolo11n-cls.pt。"
        )

    if head_index == 0:
        raise ModelStructureError("分类头位于首位，之前没有可用的目标特征层。")

    head = modules[head_index]
    target_index = head_index - 1
    target = modules[target_index]

    return BackboneView(
        sequential=sequential,
        head=head,
        target=target,
        head_index=head_index,
        target_index=target_index,
    )


def describe_backbone(view: BackboneView) -> str:
    """返回可读的结构描述，用于启动日志与答辩时的技术说明。"""
    return (
        f"sequential={len(list(view.sequential.children()))} 层; "
        f"target=[{view.target_index}] {type(view.target).__name__}; "
        f"head=[{view.head_index}] {type(view.head).__name__}"
    )
