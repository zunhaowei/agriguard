# 禾目 AgriGuard — 作物病虫害智能诊断与精准处方系统

面向小农户的 AI 作物病虫害诊断 Web 应用：拍一张病叶照片，秒出病害识别结果、分布外（OOD）可信度评估与通俗化防治处方。

## 功能特性

- **拍照即诊断**：上传单张叶片照片，自动完成拍摄质量校验（叶片占比、背景纯净度），识别病虫害类别及置信度。
- **精准识别**：基于 YOLOv8/YOLO11 分类模型（检测头 + 分类型头），支持苹果、番茄、玉米、葡萄、马铃薯、辣椒、桃、草莓、樱桃、大豆、蓝莓、南瓜、树莓、柑橘等作物共 38 类板千个类别（含健康态）。
- **OOD 拒识机制**：计算输入特征与类别原型的最大余弦相似度，对分布外/严重域偏移图片给出「拒识 + 仅供参考」双阈值处理，避免错误诊断。
- **可视化热力图**：对识别结果生成 Grad-CAM 热力图，标注模型关注的叶片区域，增强结果的可解释性。
- **通俗化处方**：内置模板生成防治处方；配置环境变量后可切换为大模型（通义千问等）个性化处方，含严重程度、生物防治、化学用药与日常管理建议。
- **纯静态前端**：零构建依赖，浏览器直接访问，手机/桌面通用。

## 技术栈

| 层次 | 技术 |
| ---- | ---- |
| 后端 | Python 3.12 · FastAPI · Uvicorn |
| 模型 | Ultralytics YOLO · PyTorch · OpenCV · Grad-CAM |
| 前端 | 原生 HTML / CSS / JavaScript（纯静态） |
| 可选 LLM | OpenAI 兼容接口（默认通义千问 qwen-plus） |

## 项目结构

```
agriguard/
├── backend/app/          # FastAPI 后端
│   ├── main.py           # 入口 + /predict 接口
│   ├── config.py         # 路径与 LLM 配置
│   ├── schemas.py        # 数据模型
│   ├── detector.py       # YOLO 病害识别 + OOD 检测
│   ├── prescriber.py     # 大模型/模板处方生成
│   ├── precheck.py       # 拍摄质量校验
│   └── gradcam.py        # Grad-CAM 热力图生成
├── frontend/             # 纯静态前端（index.html / app.js / styles.css）
├── scripts/              # 数据下载与训练脚本
├── models/               # 训练好的权重（best.pt 等）
├── data/                 # 数据集（PlantVillage），体积大不入库
├── requirements.txt
├── setup.bat             # 一键安装环境
└── run.bat               # 一键启动服务
```

## 快速开始

前置要求：已安装 **Python 3.12**（`py -3.12` 可用）。

1. **安装环境**：双击 `setup.bat`
   - 自动创建 `.venv` 虚拟环境；
   - 优先安装 PyTorch 2.5.1（CUDA 12.1 版，阿里云镜像）；若 CUDA 版下载失败或没有 GPU，自动回退安装 CPU 版 PyTorch（清华镜像）；
   - 无需 GPU 也能运行（自动回退 CPU）。
2. **启动服务**：双击 `run.bat`，浏览器访问 http://127.0.0.1:8000
3. 上传一张叶片照片，查看诊断结果、可信度、热力图与防治处方。

> **提示**：若从其它设备复制本项目，请先删除 `.venv` 再运行 `setup.bat`，否则旧的虚拟环境指针会失效。

### 手动启动（等价命令）

```bash
# Windows PowerShell / CMD
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 首次联网安装 PyTorch 较大（约 2–3 GB），请耐心等待。

## API 说明

- `GET /` — 前端页面
- `GET /health` — 健康检查，返回 `{"status": "ok"}`
- `POST /predict` — 诊断接口，`multipart/form-data` 上传字段 `file`
  - 命中 OOD 拒识时：`ok=false`，同时返回模型原始 top3 判定供参考
  - 正常识别时：返回 `detections`（Top 结果与置信度）、`prescription`、`heatmap_url`、`ood_score`

## 模型训练

```bash
python scripts/train.py --data data/plantvillage --epochs 30 --imgsz 224
# 将 runs/agriguard/weights/best.pt 复制到 models/best.pt
```

未放置 `best.pt` 时，系统会加载通用预训练权重（`yolo11n.pt`）供接口联调，识别结果无实际意义；替换权重后即为真实病害识别。

## 大模型处方（可选）

默认使用内置模板生成处方。配置环境变量后启用大模型个性化处方：

```bash
set LLM_API_KEY=你的key
set LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set LLM_MODEL=qwen-plus
```

也可在项目根目录新建 `.env` 文件（模板见 `.env.example`），配置后启动服务即自动加载。**` .env` 已加入 `.gitignore`，不会提交到仓库。**

## 参赛合规

本作品使用 AI 辅助开发，材料已标注「AI 辅助制作」；双盲评审材料不含院校/导师/单位信息。

## License

本项目仅用于学习与研究交流。模型训练数据来源于公开的 PlantVillage 数据集，CardiffUniversity 等第三方版权归原作者所有。