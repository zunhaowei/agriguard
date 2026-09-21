# 禾目 AgriGuard — 作物病虫害智能诊断与精准处方系统

面向小农户的 AI 作物病虫害诊断 Web 应用：拍一张病叶照片，秒出病害识别结果与通俗化防治处方。

> **接手本项目请先读 [`docs/工作交接.md`](docs/工作交接.md)** —— 会话连续性交接文档，
> 含当前状态快照、正在进行的工作、不可违反的红线与踩坑清单。
> 每次工作收尾都必须更新它（契约见该文档 §9）。

## 项目结构

```
agriguard/
├── backend/app/          # FastAPI 后端
│   ├── main.py           # 入口 + /predict 接口
│   ├── config.py         # 路径与 LLM 配置
│   ├── schemas.py        # 数据模型
│   ├── detector.py       # YOLO 病害识别
│   └── prescriber.py     # 大模型/模板处方生成
├── frontend/             # 纯静态前端
├── scripts/              # 数据下载与训练脚本
├── models/               # 训练好的权重（best.pt）
├── data/                 # 数据集
├── requirements.txt
├── setup.bat             # 一键安装环境
└── run.bat               # 一键启动服务
```

## 快速开始

1. 安装环境：双击 `setup.bat`（首次约需几分钟，需联网下载 PyTorch）
2. 启动服务：双击 `run.bat`
3. 浏览器打开 http://127.0.0.1:8000

## 模型训练

```bash
python scripts/train.py --data data/plantvillage --epochs 30 --imgsz 224
# 将 runs/agriguard/weights/best.pt 复制到 models/best.pt
```

未放置 `best.pt` 时，系统会加载通用预训练权重用于接口联调，识别结果无实际意义，替换权重后即为真实病害识别。

## 大模型处方（可选）

默认使用内置模板生成处方。配置环境变量后启用大模型个性化处方：

```
set LLM_API_KEY=你的key
set LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set LLM_MODEL=qwen-plus
```

## 参赛合规

本作品使用 AI 辅助开发，材料已标注「AI 辅助制作」；双盲评审材料不含院校/导师/单位信息。