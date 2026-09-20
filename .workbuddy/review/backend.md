# 禾目 AgriGuard · 后端深度审查报告

- **审查人**：贝洛奇（后端工程师）
- **日期**：2026-09-20
- **范围**：`CNDS/backend/app/` 全部 7 个 py（1422 行）、`requirements.txt`、`run.bat`、`setup.bat`、`.env.example`、`.gitignore`、`README.md`、`scripts/verify_pipeline.py`，以及**实际安装的依赖库源码**
- **性质**：**只读审查**——未改动任何项目源码、未新增项目内文件（探针脚本与原始输出写在系统临时目录 `%TEMP%\ag_probe\`）
- **方法**：源码逐行取证 → 在第三方库源码里核对调用契约 → **真机实测**（`CNDS\.venv`，RTX 4060 Laptop / torch 2.13.0+cu126 / ultralytics 8.4.137 / opencv 5.0.0 / starlette 1.6.0 / fastapi 0.141.1）→ 起真实 uvicorn 打真实 HTTP 请求复现
- **与 `architect.md` 的关系**：架构审查提出的 5 条 blocking 我逐条复核后**全部成立**，本报告不重复其结论，而是**补齐实测证据、修正其中 1 条的成因描述、并新增 12 条独立发现**（含 4 条对总监预设假设的**否证**）

---

## 0. 结论速览

1. **演示形态结论**：本机离线演示**能零故障跑通**（已实测端到端 200），但有 **3 个"演示前必须堵掉"的确定性翻车点**：冷启动首次点击卡 6.77 秒、用户上传手机原图使单次请求从 0.10s 涨到约 2.1s（热力图层 1.57s）、任何未捕获异常导致中文界面冒出英文报错。
2. **最严重的问题不是"崩溃"，是"沉默"**：4 类常见 `.env` 写法会**静默让大模型失效**（实测）、LLM 失败被 `except` 吞掉后**对外仍宣称是 AI 处方**、Grad-CAM 失败静默返回 `None` 前端只当"没有热力图"。这些在演示时表现为「功能悄悄没了」，且**没有任何日志可查**。
3. **算法层的 3 个"看似缺陷"经实测为否证**：缺少 ImageNet 归一化（否证：该权重全链路 `mean=0/std=1`）、`conf=0.25` 影响分类（否证：`conf=0.99` 与 `0.25` 的 top5 索引完全相同）、`top5` 长度不可控（否证：实测恒为 5，取 Top3 正确）。**不要改这三处**，改了是引入回归。
4. **真正被漏掉的算法一致性缺陷是几何**：识别走「短边 Resize + 中心裁剪 224」，可视化走「直接拉伸到 640」，二者在非正方形照片上**不是同一视野**；而热力图又被画在整图上。现有 demo 图是 256×256 正方形，所以两条路径恰好等价——**这就是缺陷一直没被看见的原因**。
5. **一个必须知道的事实**（影响答辩叙事）：在当前演示图上，最终热力图 **96.6% 的着色像素来自 HSV 色温异常启发式通道，Grad-CAM++ 本体只贡献约 4.0%**（实测 5318 / 5505 px）。对外讲"Grad-CAM++ 高分辨率定位病灶"时，图的形状基本不来自 Grad-CAM。

---

## 1. 实测基线（本报告所有数字的来源，均为真机测得）

| 指标 | 实测值 | 备注 |
|---|---|---|
| `Detector.load()` 首次加载 | **3.20s / 5.88s**（两次运行） | 3.28MB 权重 + CUDA 上下文初始化 |
| `/predict` **第一次**请求（冷） | **6.77s** | 模型惰性加载 + 首次前向预热全在这一跳里 |
| `/predict` 第二次请求（暖） | **0.10s** | 256×256 demo 图全链路 |
| `model.predict` 暖态单次 | **0.046s** | |
| `check_leaf_and_background` @256² | < 0.01s | |
| `generate_cam` @256² | **0.032s** | 与交接文档 7.6/7.7 宣称的 0.10～0.11s 同量级 |
| `check_leaf_and_background` @12MP(4000×3000) | **0.312s** | |
| `leaf_foreground_mask` @12MP | **0.063s** | |
| `detector.detect` @12MP | **0.178s** | |
| `generate_cam` **@12MP 原图** | **1.573s** | **比 256² 慢 49 倍**；文档口径 0.10s 不覆盖该场景 |
| 12MP 手机照片 `/predict`（含冷启动） | **3.99s** | 该样例 ood=0.2295 被拒识，未跑 gradcam |
| `ood_score`（合规 demo 图） | **0.3691** | 与 2026-09-15 日志记录的 0.3691 **完全一致**（可复现） |
| demo 图 top1 / top5conf | `Tomato___Early_blight` 0.99548 / 0.00452 / **0.0 / 0.0 / 0.0** | top3-5 概率恰为 0 |
| 分类头结构 | `Classify`，`linear.weight=(38,1280)`，**`bias` 存在 (38,)** | `children()[-1]` 实测==Classify |
| 权重内置 transforms | `Resize(224, bilinear) → CenterCrop(224) → ToTensor() → Normalize(mean=[0,0,0], std=[1,1,1])` | **无 ImageNet 归一化** |
| 目标层 / 头层 | `model.model[9]`=C2PSA，`[10]`=Classify，@640 特征图 **(1,256,20,20)** | `_TARGET_LAYER/_HEAD_LAYER` 正确 |
| 两次 Otsu 阈值 | **0.3047 → 0.4141**（Δ=0.109） | 证明"重算"确实改变结果 |
| 最终着色像素来源 | 色温异常 **5318** / 总计 **5505**（**96.6%**） | Grad-CAM 本体约 220 px（4.0%） |
| `.env` 四种写法复现 | BOM→键名变 `\ufeffLLM_API_KEY`；`export A=B`→键名变 `export A B`；`"sk-x"`→值带引号；`sk-x # 注释`→值带注释 | 4 类**全部静默失效** |
| 占位 key `sk-your-key-here` | 每次请求 **+1.026s** 且**静默**回落模板 | 断网场景按 `timeout=30` 放大 |
| 畸形文件名 `a.jpg/../../x` | **HTTP 500，响应体为纯文本 `Internal Server Error`** | 用户输入可稳定触发 |
| 缺 `file` 字段 | **HTTP 422，`{"detail":[...]}`** | 非 `PredictResponse` 形状 |
| 上传 `poc.html` | **200 落盘 → `GET /uploads/<uuid>.html` 返回 200 + `text/html; charset=utf-8`** | 同源存储型 XSS 实测成立 |
| CORS 预检 | `Origin: https://evil.example` → `access-control-allow-origin: *` | 任意网页可驱动本机推理 |
| `/docs` `/openapi.json` | **200 / 200** | 默认开放 |
| uploads 目录 | 审查开始时 **264** 文件 → 测试后 **266**，**只增不减** | 被拒绝的请求同样落盘 |
| EXIF Orientation=6 | `imread` 与 `imdecode` 返回**同一方向**（400×200） | 两条解码路径一致 |

> 原始输出留档：`%TEMP%\ag_probe\out.txt`、`out2.txt`、`out3.txt`、`out4.txt`（探针脚本 `probe.py`～`probe4.py` 同目录，可重跑复现）

---

## 2. 对总监六个方向的逐条回答（**含 4 条否证**）

### 方向 1：正确性 / 边界

| 预设 | 结论 | 依据 |
|---|---|---|
| 后缀无白名单、可取到 `../../../` 之类 | **部分成立**：无白名单（真缺陷，见 P0-3），但**路径穿越不可达** | `main.py:45` 以 `uuid4().hex` 作主名、仅把用户后缀拼在末尾。构造 `a.b/../../x` 需要中间段 `uploads/<uuid>.b` **先存在为目录**，否则 `path.open("wb")` 抛 `NotADirectoryError`（实测：→500）。当前磁盘上不存在这样的目录，故**无法任意写入**。真正可被利用的是**扩展名不受限**（`.html`/`.svg`） |
| `UploadFile` 无体积上限 → `python-multipart` 会把整个文件读进内存 OOM | **上传阶段不会 OOM**，但**磁盘无限增长**，下游有 OOM 风险 | Starlette 的 `max_part_size=1MB` 只作用于**非文件字段**（`starlette/formparsers.py:183` `if self._current_part.file is None`）；文件部分写入 `SpooledTemporaryFile(max_size=1MB)`（同文件 :230），超过 1MB **溢写到磁盘**；`shutil.copyfileobj` 按 64KB 分块流式拷贝（`main.py:47`）。故上传链路是内存安全的。**但**：`cv2` 侧无像素上限——实测把 `OPENCV_IO_MAX_IMAGE_PIXELS=1000` 后仍成功解码 40000 像素图（该保护在 opencv 5.0.0 未生效），1 亿像素图的 BGR 数组约 300MB，叠加 HSV/形态学/float32 掩膜可达 1GB+ |
| 超大图打爆显存/内存 | **算力侧可控，内存侧有风险** | 12MP 实测 gradcam 1.573s 不崩；前向固定 640 与显存无关；风险点是**全分辨率 OpenCV 运算**（内存而非显存） |
| EXIF 旋转导致热力图方向错乱 | **否证** | 自造 EXIF `Orientation=6` 的 400×200 JPEG：`cv2.imread` 与 ultralytics 实际使用的 `cv2.imdecode`（`ultralytics/utils/patches.py:36-48`）返回**同一方向**。precheck / gradcam / detector 三条解码路径方向一致，不会错乱 |

### 方向 2：模型与 OOD 逻辑

| 预设 | 结论 | 依据 |
|---|---|---|
| hook 里重新 `children()[-1]` 拿 classify 是否可靠 | **当前可靠，但脆** | 实测 `children()[-1]` == `Classify`。依赖 `YOLO.model.model.model` **三级属性链 + Sequential 次序**；换 backbone（n→s）或升 ultralytics 会**静默指向别的层**（不报错，热力图语义全错）。且 `detector.py:140` 在**每次前向回调里**重复做这步推导，属无谓开销与耦合 |
| `top5` 实际长度 | **恒为 5**（`results.py:1379` 的 `[:5]`），`min(3, len())` 永远等于 3 | 实测 `type=list, len=5`。**不是缺陷**，但 `min()` 是无效保护，掩盖了"这个模型固定 38 类"的事实 |
| `conf=0.25` 用在分类上有意义吗 | **否证：完全无意义（no-op）** | 实测 `conf=0.99` 与 `conf=0.25` 的 top5 索引/置信度**逐位相同**；`models/yolo/classify/predict.py:72-90` 的 `postprocess` 不做任何阈值过滤（`conf` 只服务检测/分割的 NMS） |
| `_ood_score` 忽略 `classify.linear.bias` 使"余弦相似度"名不副实 | **名实相符，但语义是启发式而非概率** | bias 确实存在（实测 shape (38,)，`max\|b\|=1.3018`）；忽略 bias 后 38 类**排序发生变化**（实测 True），但该图 `argmax(cos)==argmax(logit)==argmax(softmax)==29`。结论：`ood_score` 定义为"与类权重向量的最大余弦相似度"**表述准确**；问题在于它**没有概率意义、没有标定**——合规图仅 0.3691，而 logits 高达 24.3、softmax 0.9955，说明分数被权重向量的方向/尺度分布主导。实证其脆弱性：日志记录**枫叶 0.33 > 0.32 → 被判"正常"并识别为番茄·斑枯病**（`2026-09-01.md:62`），即 OOD 门存在**已被记录在案的假阴性** |

### 方向 3：Grad-CAM 正确性

| 预设 | 结论 | 依据 |
|---|---|---|
| 缺少 ImageNet 归一化是真实缺陷 | **否证** | 实测打印权重内置 transforms：`Normalize(mean=tensor([0.,0.,0.]), std=tensor([1.,1.,1.]))`（`ultralytics/data/augment.py:24-25` 的 `DEFAULT_MEAN/STD` 即 0/1）。**训练、推理、Grad-CAM 三处都只做 `/255`，尺度完全一致**。所以"归一化缺失"不成立；`gradcam.py:172` 的 `/255.0` 是对的 |
| 真实缺陷在哪 | **几何不一致（这才是真缺陷）** | 权重内置 `Resize(224 短边) + CenterCrop(224)`；`detector.detect` 走 ultralytics 管线会应用它（`models/yolo/classify/predict.py:53-60`），即**模型看到的是"短边缩放后中心裁剪的 224"**。而 `gradcam.py:161` 是 `cv2.resize(img, (640,640))` —— **无保持宽高比的缩放、无中心裁剪**，直接在拉伸图上算 CAM，再 `gradcam.py:214` 放大回**整图**。非正方形照片上（手机 4:3/16:9）模型视野与热力图坐标系不一致，定位可系统性偏移；叶片偏心时，CAM 解释的区域甚至可能落在模型根本没看过的位置 |
| 为什么现在"看着对" | **两个原因，都可核查** | ① 现有 demo 图 `_demo_leaf_compliant.jpg` 是 **256×256 正方形**，`Resize(224)+CenterCrop(224)` 与 `resize(640,640)` 在几何上等价（仅尺度差异），所以两条路径在当前素材上**恰好一致**——换个构图就露馅；② Grad-CAM 对**纯尺度**扰动本就鲁棒（特征图分辨率变了但梯度加权的位置不变），所以尺度差异不显现，**几何形变**才显现 |
| `heat_color`（约 225 行）是死代码 | **证实** | 实测同一张图两次计算：thr 0.3047 vs 0.4141，掩膜 278 px vs 5505 px，`heat1 & ~heat2` = 58 px、`heat2 & ~heat1` = 5285 px → **两次结果不同，第 225 行的赋值在第 239 行被覆盖，属死存储**（`gradcam.py:221-225` 整段无效） |
| 异常区 0.85 超阈值上限，重算 Otsu 是否真的改变结果 | **改变，但不是文档说的那个机制** | 异常区 `cam=0.85 > _THRESHOLD_MAX=0.50 ≥ thr`，**无论重算与否都必然被涂色**（文档结论正确但无关）；重算的**真实副作用**是把阈值从 0.3047 抬到 0.4141（+36%），**挤掉了 58 个原本会着色的 Grad-CAM 弱病灶像素**（`heat1 & ~heat2` = 58）。即异常通道会**轻微压制** Grad-CAM 的弱响应 |
| 额外发现（重要） | **最终热力图 96.6% 来自色温异常通道** | 5318 / 5505 px。Grad-CAM 本体仅约 220 px。对外宣称"Grad-CAM++ 定位病灶"与实际成图来源不符，见 P1-6 |
| `cam` 数值边界 | **机制成立、当前图未触发** | `cv2.resize(..., INTER_CUBIC)` 过冲实测：随机 20×20 → 400×400 出现 `max=1.094`、1143 px > 1；而 `np.uint8(255*1.05)` = **11（回绕成冷色）**。当前 demo 图实测 `max=0.9986`、0 px > 1（有 3903 px 负过冲，但负值被 `cam > thr` 掩膜挡掉，无害）。放大倍数越大（20×20→4000×3000 是 200 倍）越易触发 → 一行 `np.clip` 即可根治 |

### 方向 4：配置与密钥

| 预设 | 结论 | 依据（**全部实测**） |
|---|---|---|
| 手写解析不处理引号 / `export` / 行尾注释 / BOM | **证实，且 4 类写法导致静默失效** | `utf8_bom` → 键名变 `\ufeffLLM_API_KEY`（`read_text(encoding="utf-8")` 不剥 BOM）→ **LLM_API_KEY 为空、静默走模板**；`export LLM_API_KEY=sk-exp` → 键名变 `export LLM_API_KEY` → 失效；`LLM_API_KEY="sk-quoted"` → 值带引号 → `Bearer "sk-…"` → 401 → 静默降级；`LLM_API_KEY=sk-x # note` → 值含注释。**四种都是编辑器/文档里极常见的写法，且失败时没有任何提示** |
| `os.environ.setdefault` 的隐患 | **证实** | 实测：外部已设 `LLM_API_KEY=""`（空串）时 `setdefault` **不写入** .env 的值 → 键值为空 → 静默走模板；反之，环境里残留的旧 key 会**静默盖过**项目 .env，排查时极易误判 |
| `.env.example` 的 `sk-your-key-here` 被误复制会怎样 | **证实：每次请求多打一次注定失败的外部调用，且不报错** | `prescriber.py:20` `if LLM_API_KEY:` 对 `"sk-your-key-here"` 判真 → 实测每次 `generate()` **+1.026s**（经代理环境）→ 401/异常被 `except` 吞掉 → 模板兜底。**断网场景**：`timeout=30` 是 `(connect=30, read=30)` 双段超时，最坏 30s（连接）+ 30s（读）≈ **60s**；且该等待发生在 `async` 路由内 → **整个事件循环冻结，连 `/health` 和静态资源都不响应**（实测 timeout=3 时耗时 3.02s，线性外推成立） |

### 方向 5：网络调用健壮性

- **不区分连接/读超时**：`requests.post(..., timeout=30)`（`prescriber.py:47`）为单个浮点，urllib3 解释为 connect=30 且 read=30，无法单独调小连接等待。**量化：最坏约 60s（30+30）**，且发生在同步代码被 `async` 包装的路由内 → 全站假死。
- **不检查 `r.status_code`**：`r.json()["choices"]`（`:49`）在 401/429/5xx 时抛 `KeyError`/`JSONDecodeError` → 被 `:51` 吞掉。**功能不崩，但错误完全不可见**。
- **不处理 markdown 代码块包裹**：模型返回 ```` ```json\n{...}\n``` ```` 时 `json.loads` 抛异常 → 静默降级为模板。虽然开了 `response_format={"type":"json_object"}`，但该参数**并非所有兼容端点都强制生效**，属已知的常见返回形态。
- **`Prescription(**json.loads(content))` 字段缺失即抛异常**：Pydantic 校验失败 → 同样被吞。
- 结论：**这条链路的"健壮性"是靠"全部静默降级"换来的**——线上表现是"处方看起来正常，其实全是死模板"。建议：`(connect, read) = (3, 20)` 分离、检查 `status_code`、剥 code fence、`logger.warning` 记录降级原因。

### 方向 6：安全

| 项 | 实测结论 | 风险定性 |
|---|---|---|
| CORS `*` × `*` × `*` | 预检对 `Origin: https://evil.example` 返回 `access-control-allow-origin: *` | 无鉴权 + 通配来源 → **任意网页可在受害者浏览器里驱动本机推理**（把演示机当免费 GPU 推理后端/DoS 它），并可读取响应。本机 127.0.0.1 绑定可挡住局域网，挡不住"用户自己打开了一个网页" |
| `/uploads` 长期公开 | 264→266 文件只增不减；被拒绝的请求（12MP 图、poc.html）**同样落盘** | ① 用户照片长期留存（隐私）；② uuid4 随机名**不可枚举**（这点风险有限）；③ **任意扩展名可写 + 同源以 `text/html` 提供 → 存储型 XSS 实测成立**（`GET /uploads/<uuid>.html` → 200 `text/html`，脚本可执行，且同源下可继续调用本机 API） |
| 无鉴权 / 无限流 | 确认：无任何认证、无速率限制、无 CSRF 考量 | 演示场景可接受（127.0.0.1），但需与 CORS 收敛配合 |
| `serve_panel.bat` 用 `http.server` 托管项目根 | 确认（`:6`，工作目录=项目根）→ 一旦补上真 `.env`，`http://127.0.0.1:8001/.env` 即可被读 | 与"补 .env"必须**同批处理** |
| `/docs` `/redoc` `/openapi.json` | 均 200 开放 | 演示环境两面性：对评委展示 API 是加分项，但暴露内部字段与错误结构。建议**保留 `/docs`**（讲解用）但**收敛 CORS 与上传**，二者不冲突 |
| uvicorn 未绑 127.0.0.1 的风险 | `run.bat:12` 已绑 `--host 127.0.0.1`，正确 | 建议在 `run.bat` 里加注释固化此约束；若为"手机连同一 WiFi 演示"改成 `0.0.0.0`，则 **CORS `*` + 无鉴权 + 上传无白名单** 三项风险同时被放大到局域网，必须同步修 |

---

## 3. A. 缺陷清单

### P0（阻塞级：正确性缺陷 / 需求未满足 / 契约安全数据完整性破坏）

#### P0-1【正确性缺陷】"降级回退"实为联网下载 + 必然 AttributeError

- **证据**：
  - `backend/app/config.py:11` → `FALLBACK_MODEL = "yolo11n.pt"`
  - `backend/app/detector.py:126-128` → `self.model = YOLO(FALLBACK_MODEL)`（相对名，非绝对路径）
  - `backend/app/detector.py:131-132` → 无条件 `list(self.model.model.model.children())[-1].conv.register_forward_hook(...)`
  - **实测事实**：`models/` 目录下只有 `best.pt`、`best_old.pt`、`yolo11n-cls.pt`——**`yolo11n.pt` 不存在**；而正确的分类兜底权重 `models/yolo11n-cls.pt` 就在同目录却未被引用。
  - `README.md:37` 承诺"未放置 best.pt 时，系统会加载通用预训练权重用于接口联调"——与实现相反。
- **后果链**：`best.pt` 缺失/改名/被安全软件隔离 → ① ultralytics 尝试**联网下载** `yolo11n.pt`（本项目历史记录明确 github 被拦、离线演示必挂）→ ② 即便下载成功，`yolo11n.pt` 是**检测**模型，`Detect` 头没有 `.conv` 属性 → **`AttributeError`** 而非降级 → ③ 该异常发生在 `detect()` 内（`main.py:59` 无 try）→ **HTTP 500**。
- **注（修正架构报告口径）**：不是"启动即崩"，而是"**首个 `/predict` 请求崩**"——`Detector.__init__` 只置 `None`，加载发生在 `detect()` 里（`detector.py:156-157`）。服务仍能启动、`/health` 仍 200，**故障被推迟到评委面前的那一刻**，性质更坏。
- **触发概率**：演示机重装、`.venv` 重建、目录迁移、杀软误隔离——都不罕见。

#### P0-2【契约破坏】无全局异常处理器，错误响应不是 `PredictResponse`

- **证据**：`backend/app/main.py` 全文 94 行**没有任何 try/except，也没有 `@app.exception_handler`**。
- **实测**：
  - 畸形文件名 `a.jpg/../../x`（用户输入）→ **HTTP 500，响应体为纯文本 `Internal Server Error`**
  - 缺 `file` 字段 → **HTTP 422，`{"detail":[{"type":"missing",...}]}`
- **后果（前端实测行为）**：`frontend/app.js:82` `r.json()` 对纯文本 500 抛 `SyntaxError` → `.catch` 显示 **"诊断失败：Unexpected token I in JSON at position 0"**；对 422 则 `r.json()` 成功 → `data.ok` 为 `undefined`（不等于 `false`）→ 进入**成功分支** → `app.js:157` `data.detections.forEach` 抛 `TypeError` → 结果区已被 `app.js:138` 置为可见但内容为空，用户看到**一个空白"诊断结果"卡片 + 一行英文报错**。
- **期望**：所有错误路径返回同形状 `{"ok": false, "reason": "…中文可读原因…"}`，并 `logger.exception` 记录。

#### P0-3【契约安全】上传无类型白名单 → 任意内容落盘 + 同源 `text/html` 提供（存储型 XSS 实测成立）

- **证据**：`main.py:44` 后缀完全取自用户文件名、无白名单；`main.py:29` `/uploads` 静态挂载；无任何清理逻辑。
- **实测（真实 uvicorn + 真实 HTTP）**：
  - 上传 `poc.html`（内容含 `<script>`）→ HTTP 200，返回 `ok=false` 的**友好拒绝**，**但文件已落盘** `uploads/d6c943203eb54e579bd6736148f13a9d.html`（74 bytes）
  - `GET http://127.0.0.1:8012/uploads/d6c943203eb54e579bd6736148f13a9d.html` → **200，`content-type: text/html; charset=utf-8`，脚本原样返回**
  - 被 OOD 拒绝的 12MP 照片同样留在 `uploads/`（本次会话新增 2 个文件，目录 264 → 266）
- **后果**：① 同源存储型 XSS（攻击者可借受害者浏览器调用本机无鉴权 API、读取其它已泄露 URL 的图片）；② 磁盘无界增长；③ 用户照片长期留存（隐私）。
- **附带**：无体积上限（`MAX_UPLOAD_BYTES` 不存在），结合"`OPENCV_IO_MAX_IMAGE_PIXELS` 实测未生效"，巨图是内存风险。

#### P0-4【正确性缺陷】`async` 路由内全同步阻塞 + 单例共享可变状态竞态

- **证据**：
  - `main.py:42-94`：`async def predict` 内顺序执行 `shutil.copyfileobj`、OpenCV、`detector.detect`（YOLO 前向）、`generate_cam`（一次 640 前向 + 反传）、`prescriber.generate`（**同步 HTTPS，可阻塞 30~60s**）——**事件循环全程被占住**
  - `detector.py:111,138-142`：`_penultimate_features` 是 forward hook 写入的**实例级可变状态**，读写之间存在竞态窗口
  - `gradcam.py:168-170,253-254`：并发调用会**全局**改 `requires_grad` 再恢复，两个请求交叉时可能一边在反传、另一边已把 `requires_grad` 复位
  - `gradcam.py:176-186`：向**共享模型**注册 forward hook
  - `main.py:25-26`：`detector`/`prescriber` 是模块级单例
- **实测**：冷启动首请求 **6.77s**、暖态 **0.10s**；黑洞地址 `timeout=3` 实测耗时 3.02s（线性外推 `timeout=30` → 约 30s）。
- **后果**：演示时一次慢调用（LLM）→ **`/health`、`/static/app.js`、CSS、图片全部无响应**；评委此时刷新页面会看到"站点打不开"。竞态表现是"热力图偶尔不显示"（被 `gradcam.py:255` 静默吞掉，无日志）。

#### P0-5【需求未满足】"大模型个性化处方"实为死模板，且**无来源标识**；`.env` 四类写法静默失效

- **证据**：
  - `config.py:21` `LLM_API_KEY` 默认空；`.env` 实测不存在 → `prescriber.py:20-22` 直接走 `_generate_from_template`
  - `prescriber.py:51-52` `except Exception: return self._generate_from_template(top)` ——**无日志、无标识**，对外与"AI 处方"完全同形
  - `schemas.py:12-18` `Prescription` **无 `source` 字段**，响应无法区分 LLM/模板
  - `README.md:41` / `docs/产品介绍文案.md`：以"通义千问大模型个性化处方"为核心卖点
  - **实测**：`severity="待评估"` 是模板的唯一可辨指纹；用 `.env.example` 的占位 key 时每次请求 +1.026s 后**仍静默回落模板**
- **期望**：`PredictResponse` 增加 `prescription_source: "llm" | "template"`；演示前配置真实 key 并端到端留证；`.env` 解析改用 `python-dotenv`（依赖已装）并对占位/畸形值在**启动时**报错。
- **附带（模板内容质量）**：模板 `chemical` 为"科学用药，坚持减量增效…"——**无具体药剂、无用量**，与文案宣称的"推荐药剂、用量、施药方式"不符；答辩若追问会直接暴露。

---

### P1（高：影响演示效果、可辩护性或可复现性）

#### P1-1【正确性/一致性】Grad-CAM 与识别路径**几何不一致**（非归一化问题）
- 证据：实测权重内置 `Resize(224 短边)+CenterCrop(224)`（`classify/predict.py:53-60` 应用之）vs `gradcam.py:161` 的 `cv2.resize(img,(640,640))`（拉伸变形、无中心裁剪）→ `gradcam.py:214` 又放大回**整图**。
- 为什么现在看不出：`_demo_leaf_compliant.jpg` 是 256×256 正方形，两条路径在该素材上几何等价。
- 影响：非方图/偏心叶上，热力图定位与模型真实视野不一致 → "可解释性"这一答辩得分点的技术可靠性被削弱。
- **不是崩溃项，但属于"被问就答不上来"的技术缺陷。**

#### P1-2【效果与声明不一致】最终热力图 96.6% 来自色温异常启发式，Grad-CAM 本体仅约 4.0%
- 实测：色温异常 5318 px / 最终着色 5505 px。Grad-CAM 本体约 220 px（`heat1` 278 px 中 cam>0.4141 的部分）。
- 影响：答辩/材料若强调"Grad-CAM++ 高分辨率定位病灶"，与成图来源不符；评委问"热力图为什么是这个形状"时，诚实答案是"主要是 HSV 色温异常统计"。**建议如实描述两通道贡献，或调参让两通道可分辨。**
- 附带：`_ANOMALY_HEAT` 是**固定 0.85**，异常区无论轻重都涂成同一档暖色 → 无法表达严重度（与架构师建议的"严重度量化"方向冲突，需一并设计）。

#### P1-3【安全】CORS 通配 + 上传目录公开可访问
- 实测预检返回 `access-control-allow-origin: *`；`/uploads` 无鉴权、无过期。
- 期望：`allow_origins=["http://127.0.0.1:8000"]`（+ 环境变量覆盖），保持 `allow_methods=["GET","POST"]`、`allow_headers=["Content-Type"]`。

#### P1-4【演示体验】冷启动首次点击卡 6.77 秒，前端只有一行静态文案
- 证据：`main.py:25-26` 单例惰性加载；`detector.py:156-157` 首个请求才 `load()`；`app.js:77` 仅 `status.textContent="正在校验图片…"`（无 spinner、无禁用、无超时）。
- 实测：冷 6.77s / 暖 0.10s。**巡展第一次演示必然发生**（进程刚起）。
- 期望：`lifespan` 预热（`load()` + 一次 dummy 224 前向）；前端加载态（前端报告已覆盖，后端需配合预热）。

#### P1-5【可复现性】依赖未锁定、缺 torch、CUDA 版本漂移
- 证据：`requirements.txt:8` `ultralytics>=8.2`（**8.4.153 已知与 forward hook 冲突**，实测可用版本 8.4.137）；全文**无 torch/torchvision**；`numpy>=1.24`/`opencv-python>=4.9` 无上限；`setup.bat:18` 装 `cu121` 而实际环境是 `+cu126`；`python-dotenv` 已装却不在清单。
- 影响：换机/重装即可能不可复现——这直接冲击竞赛"技术方案"与"佐证材料真实有效"。

#### P1-6【可诊断性】零日志 + 两处静默吞错
- 证据：全仓无 `logging` 配置；`gradcam.py:255-256` `except Exception: return None`；`prescriber.py:51-52` `except Exception: → 模板`。
- 影响：现场故障**无任何日志可查**（这是"现场零故障"能力的底线）；"热力图没了"与"模型没认出"在日志上无法区分。

#### P1-7【文档口径失真】"单张热力图 0.10s"仅对 256×256 素材成立
- 证据：实测 `generate_cam` @256² = 0.032s；**@12MP = 1.573s（慢 49 倍）**；`check_leaf_and_background` @12MP = 0.312s。
- 影响：`开发交接文档.md` 7.6/7.7 两处"0.10s/0.11s 对前端体验无影响"若被评委按真实手机照片追问，口径对不上。建议补一句测条件（256×256 demo 图）。

---

### P2（中低：质量、边界、卫生）

| # | 缺陷 | 证据 | 说明 |
|---|---|---|---|
| P2-1 | `_class_names`/`_disease_cn`（40 行）为死代码，且是**潜伏陷阱** | `detector.py:10-49,100-105` | `_CN_BY_NAME` 已覆盖全部 38 类（实测 `names` 与其对齐），`___` 分支永不触发；且该分支的 key 格式与真实类名前缀不符（`"Corn"` vs `"Corn_(maize)"`）——**一旦将来触发会直接回落英文** |
| P2-2 | `gradcam.py:221-225` 死存储 | 实测两次 thr/掩膜不同 | 5 行无效代码，且"重算 Otsu"抬高阈值挤掉 58 px Grad-CAM 弱病灶 |
| P2-3 | `cam` 越界未裁剪 | 实测机制成立（随机图 → 1.094，`np.uint8(255*1.05)=11` 回绕）；当前 demo 图 max=0.9986 未触发 | 加 `np.clip(cam,0,1)` 一行根治 |
| P2-4 | `conf=0.25` 是分类任务的 no-op | 实测 conf 0.25/0.99 结果逐位相同；`classify/predict.py:72-90` | 语义噪音，建议删除或加注释说明 |
| P2-5 | Top3 里两项置信度为 0.0 仍被渲染 | 实测 `top5conf=[0.99548,0.00452,0,0,0]`；`app.js:157-167` 全量渲染 | 演示图上会出现两行 "0.0%"，观感差且无信息量；后端可只返回 `conf>0` 的项或前端过滤 |
| P2-6 | `ood_score` 语义需更准确的对外表述 | 同上方向 2；`2026-09-01.md:62` 枫叶 0.33 被放行 | 建议文档/前端统一改为"分布相似度（启发式，非概率）"，并说明已知假阴性 |
| P2-7 | `config.py:27-28` import 期 mkdir 副作用；`DATA_DIR` 无人使用 | `config.py:6,27-28`（全仓仅此处引用 `DATA_DIR`） | 仅 `UPLOAD_DIR`/`MODELS_DIR` 需要；建议移入显式 `ensure_dirs()` |
| P2-8 | `.env.example` 的占位值易致误配 | `.env.example:5` | 建议改为 `LLM_API_KEY=`（空）+ 注释"留空即使用模板处方" |
| P2-9 | `.gitignore:21` 忽略 `runs/` | `runs/agriguard_v2/results.csv|confusion_matrix*.png` 是参赛证据 | 一旦 `git init`，**佐证材料不会进版本控制**；建议改为 `runs/**/weights/`，保留 csv/png |
| P2-10 | 无 `.git` | 全仓无 `.git` | 架构师已提；从后端角度补充：这使"可回滚重构"与"改动时间线"两个原创性叙事都缺证据 |
| P2-11 | `verify_pipeline.py` 覆盖缺口 | `scripts/verify_pipeline.py:61-123` | 未覆盖：① 非图片文件 ② 畸形文件名（500 路径）③ 上传体积/类型拒绝 ④ `heatmap_url` 指向的文件是否真的存在 ⑤ 并发 ⑥ `prescription_source`。建议补 3 条（②③④）即可闭合最主要风险 |
| P2-12 | `/health` 与 `/predict` 响应形状不统一 | `main.py:37-39` | 无 `{code,data,message}` 统一外壳；**但不要为了"规范"去改 `/predict`**——前端 `app.js:92-203` 强依赖当前扁平形状，改动即引入回归。仅记录在案 |

---

## 4. B. 修复方案（可直接落地）

> 通用前提：以下改动均**不触碰**算法阈值（`ood_*_threshold`、`LEAF_MIN_RATIO`、`_THRESHOLD_MIN/MAX`、`_ANOMALY_SIGMA`、`_HEAT/ENOUGH*`）与 `models/best.pt`。每项标注**对现有演示效果的影响**与**回归安全性**。
> 回归基线：`scripts/verify_pipeline.py` 5 项（health / 背景拒绝 / OOD 拒绝+top3 / 正常识别 / 警告区间）。该脚本全部请求都用 `filename="*.jpg"` 且图 <1MB、内容是真图片 → **P0-2/P0-3/P0-4 的修复对它无害**。

### FIX-1（P0-1）兜底模型改为同目录的分类权重 + 结构断言

```python
# ---------- 改前 config.py:10-11 ----------
MODEL_PATH = MODELS_DIR / "best.pt"
FALLBACK_MODEL = "yolo11n.pt"
```
```python
# ---------- 改后 ----------
MODEL_PATH = MODELS_DIR / "best.pt"
# 兜底必须是「分类」权重且必须是本地绝对路径：
# 相对名会触发 ultralytics 联网下载（离线演示必挂），且 yolo11n.pt 是检测模型（无 classify.conv）。
FALLBACK_MODEL = MODELS_DIR / "yolo11n-cls.pt"
```

```python
# ---------- 改前 detector.py:124-136 ----------
def load(self):
    if MODEL_PATH.exists():
        self.model = YOLO(str(MODEL_PATH))
    else:
        self.model = YOLO(FALLBACK_MODEL)
    classify = list(self.model.model.model.children())[-1]
    classify.conv.register_forward_hook(self._hook_fn)
    W = classify.linear.weight.detach().float()
    self._class_weights_norm = F.normalize(W, dim=1)
```
```python
# ---------- 改后 ----------
def load(self):
    source = MODEL_PATH if MODEL_PATH.exists() else FALLBACK_MODEL
    if not Path(str(source)).exists():
        raise FileNotFoundError(f"未找到可用权重：{source}（不联网下载，请确认 models/ 内容）")
    self.model = YOLO(str(source))

    self._head = self._resolve_head()          # 结构内省，不依赖层序号
    self._head.conv.register_forward_hook(self._hook_fn)
    W = self._head.linear.weight.detach().float()
    self._class_weights_norm = F.normalize(W, dim=1)

def _resolve_head(self):
    """末层必须是 Classify（具备 conv/linear/pool）。检测/分割权重在此直接报错，而不是抛 AttributeError。"""
    head = self.model.model.model[-1]
    if not (hasattr(head, "conv") and hasattr(head, "linear") and hasattr(head, "pool")):
        raise RuntimeError(
            f"加载的权重不是分类模型（末层={type(head).__name__}），"
            f"请检查 {MODEL_PATH.name} / {Path(str(FALLBACK_MODEL)).name}"
        )
    return head
```
- **影响**：`best.pt` 存在时行为**逐位不变**；缺失时从"联网下载 + AttributeError + 500"变为"用本地分类权重跑通"（识别结果无意义但服务不崩，与 README 承诺一致）。
- **回归**：5/5 不受影响（`best.pt` 在场，`_resolve_head` 实测返回 `Classify`）。
- 顺手收益：`_hook_fn` 里 `list(...children())[-1]`（`detector.py:140`）可改为 `self._head`，省掉每次前向的结构推导。

### FIX-2（P0-2）全局异常处理器 + 错误响应与成功响应同形状

```python
# ---------- main.py 追加 ----------
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("agriguard")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # 任何未捕获异常都必须返回 PredictResponse 同形状，
    # 否则前端 app.js 会走成功分支并崩在 data.detections.forEach（已实测 422/500 两种形状）。
    logger.exception("unhandled error: %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "reason": "服务内部错误，请重试；若持续出现请查看后端日志。",
                 "detections": [], "prescription": None, "heatmap_url": None},
    )
```

```python
# ---------- 改前 main.py:43-47 ----------
async def predict(file: UploadFile = File(...)):
    suffix = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{suffix}"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
```
```python
# ---------- 改后（同时落地 FIX-3；抛出的可预期错误在端点内转成 ok=False）----------
@app.post("/predict", response_model=PredictResponse)
def predict(file: UploadFile = File(...)):
    try:
        path = _save_upload(file)                       # 见 FIX-3
    except UploadRejected as e:
        return PredictResponse(ok=False, reason=str(e))
    ...
```
- **影响**：成功路径零变化；错误路径从"英文纯文本/Schema 错误"变为"中文 `ok=false`"，前端**无需改动**即可正确显示拒绝原因（走 `app.js:92` 的拒绝分支）。
- **回归**：5/5 不受影响（不触发异常路径）。

### FIX-3（P0-3）上传白名单 + 体积上限 + 落盘隔离 + 清理

```python
# ---------- 改前 main.py:44-47 ----------
    suffix = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{suffix}"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
```
```python
# ---------- 改后 ----------
ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}   # 显式排除 .svg（可执行脚本）/.html/.gif
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class UploadRejected(Exception):
    pass


def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise UploadRejected("仅支持 jpg / jpeg / png / bmp / webp 图片，请重新选择文件。")
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"      # 主名固定 uuid，后缀来自白名单
    size = 0
    with path.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                path.unlink(missing_ok=True)
                raise UploadRejected("图片超过 8MB，请压缩后重试。")
            out.write(chunk)
    return path
```
- **附加要求**：把热力图单独放 `UPLOAD_DIR / "heatmaps"` 并只挂载该子目录（`main.py:29`），原图**在响应返回前删除**（`finally`），启动时扫一遍清空历史残留。
- **影响**：**会改变现有行为**——`.svg/.html/.gif/.heic` 会被明确拒绝（原来 `.heic` 虽放行但 `cv2.imread` 返回 None → 同样失败，只是报错文案更差）。**演示用图都是 jpg → 无观感变化**。若材料里演示过 GIF/SVG，需提前换成 jpg。
- **回归**：`verify_pipeline.py` 全部用 `.jpg` 且体积小 → **5/5 通过**；但脚本第 4 项读的是 `frontend/_demo_leaf_compliant.jpg`（18KB）→ 通过。
- **注意**：清理原图后 `heatmap_url` 仍指向存在的文件 → 前端不受影响。

### FIX-4（P0-4）解除事件循环阻塞 + 串行化模型临界区 + 状态归位

```python
# ---------- 改前 main.py:42 ----------
async def predict(file: UploadFile = File(...)):
```
```python
# ---------- 改后 ----------
import threading
_model_lock = threading.Lock()     # GPU 单卡是串行资源；把"靠阻塞意外串行"变成显式串行


def predict(file: UploadFile = File(...)):     # 去掉 async → FastAPI 自动丢线程池
    ...
    with _model_lock:                          # 临界区：模型 + hook + requires_grad
        detections, ood_score, is_ood, is_warning = detector.detect(str(path))
        heatmap_url = None
        if detections and detections[0].class_id is not None:
            heat_path = UPLOAD_DIR / f"{path.stem}_heatmap.jpg"
            if generate_cam(detector.model, str(path), detections[0].class_id, str(heat_path)):
                heatmap_url = f"/uploads/{heat_path.name}"
    prescription = prescriber.generate(detections)   # 网络 I/O 放在锁外
```

```python
# ---------- detector.py：去掉实例可变状态（根因修复，优于仅加锁）----------
# 改前 detector.py:138-142
def _hook_fn(self, module, input, output):
    classify = list(self.model.model.model.children())[-1]
    pooled = classify.pool(output).view(-1)
    self._penultimate_features = pooled.detach()
```
```python
# 改后
def detect(self, image_path: str):
    if self.model is None:
        self.load()
    feats: dict = {}
    head = self._head
    h = head.conv.register_forward_hook(
        lambda _m, _i, out: feats.update(v=head.pool(out).view(-1).detach())
    )
    try:
        results = self.model.predict(image_path, conf=0.25, verbose=False)[0]
    finally:
        h.remove()                       # 用完即摘，天然并发安全，无需锁也能正确
    ...
    ood_score = self._ood_from(feats.get("v"))
```
- **影响**：成功路径的返回内容**完全不变**；事件循环解放后，LLM 慢调用期间 `/health`、`/static/*` 仍可用（这正是"现场演示不翻车"的底线）。
- **回归**：单线程语义不变 → **5/5 通过**。并发安全性提升后，`_ood_score` 的调用时机需随之调整（改为从 `feats` 取，勿再读实例属性）。
- **务必同时保留**：`gradcam` 的 `requires_grad` 切换与 hook 必须留在 `_model_lock` 内（`gradcam.py:168-170` 是全局状态，状态归位解决不了）。

### FIX-5（P0-5）配置用 python-dotenv + 占位/畸形值启动期报错 + 处方来源标识

```python
# ---------- 改前 config.py:13-19 ----------
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
```
```python
# ---------- 改后 ----------
from dotenv import load_dotenv        # python-dotenv 1.2.3 已安装

# encoding="utf-8-sig" 显式剥离 BOM：手写解析在 BOM/export/引号/行尾注释四种写法下
# 会静默失效（已实测），导致 LLM 静默降级为模板且无任何提示。
load_dotenv(BASE_DIR / ".env", override=False, encoding="utf-8-sig")
```
```python
# ---------- config.py 追加：占位值识别 ----------
_PLACEHOLDER_KEYS = {"sk-your-key-here"}
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip().strip('"').strip("'")
if LLM_API_KEY in _PLACEHOLDER_KEYS:
    logging.getLogger("agriguard").warning(
        "LLM_API_KEY 仍是 .env.example 的占位值，处方将走模板兜底；请填入真实 key 或留空。"
    )
    LLM_API_KEY = ""
```

```python
# ---------- schemas.py：PredictResponse 增加字段（向后兼容，旧前端忽略）----------
    prescription_source: Optional[str] = None   # "llm" | "template"
```
```python
# ---------- main.py 返回处 ----------
    prescription, prescription_source = prescriber.generate_with_source(detections)
    ...
    prescription=prescription, prescription_source=prescription_source,
```
- **影响**：若演示前配真实 key → 处方变成真大模型（需重跑一次端到端留证）；若维持无 key → 与现状一致，仅多一个 `prescription_source:"template"` 字段。
- **回归**：`verify_pipeline.py` 不校验该字段 → **5/5 通过**。
- **配套**：`.env.example:5` 的 `sk-your-key-here` 改为空值；`serve_panel.bat` 与"补 .env"必须**同批处理**（否则 `http://127.0.0.1:8001/.env` 可被直接读取）。

### FIX-6（P1-5）依赖锁定

```text
# ---------- requirements.txt 改后 ----------
fastapi==0.141.1
uvicorn[standard]==0.53.0
python-multipart==0.0.32
pydantic==2.13.5
numpy==2.5.3
opencv-python==5.0.0.93
pillow==12.3.0
requests==2.34.2
python-dotenv==1.2.3
ultralytics==8.4.137          # 禁止 >=8.4.153：predict 会 deepcopy 模型，与 forward hook 冲突
torch==2.13.0+cu126           # 需 -f https://mirrors.aliyun.com/pytorch-wheels/cu126/
torchvision==0.28.0+cu126
```
并把 `setup.bat:18` 的 `cu121` 改为 `cu126`（与实际环境一致）。
- **影响**：不改动当前已装环境，仅保证重装可复现。

### FIX-7（P1-6）日志与吞错

```python
# ---------- gradcam.py:255-256 ----------
# 改前
    except Exception:
        return None
# 改后
    except Exception:
        logging.getLogger("agriguard.gradcam").exception(
            "generate_cam failed (image=%s, class_idx=%s)", image_path, class_idx
        )
        return None
```
`prescriber.py:51-52` 同理，并把降级原因写成 `logger.warning("LLM 处方失败，回落模板：%s", exc)`。
- **影响**：零功能变更；现场故障可查（"是图片坏了还是模型坏了"一目了然）。

### FIX-8（P1-1）Grad-CAM 几何对齐（**唯一会改变可见输出的算法侧修复，建议放在最后做**）

```python
# ---------- 改前 gradcam.py:160-172 ----------
orig_h, orig_w = img.shape[:2]
rgb = cv2.cvtColor(cv2.resize(img, (_IMGSZ, _IMGSZ)), cv2.COLOR_BGR2RGB)
x = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to(device)
```
```python
# ---------- 改后：复刻权重内置的 Resize(短边) + CenterCrop ----------
orig_h, orig_w = img.shape[:2]
scale = _IMGSZ / min(orig_h, orig_w)
inter = cv2.resize(img, (max(_IMGSZ, int(round(orig_w * scale))),
                         max(_IMGSZ, int(round(orig_h * scale)))),
                   interpolation=cv2.INTER_LINEAR)
y0 = (inter.shape[0] - _IMGSZ) // 2
x0 = (inter.shape[1] - _IMGSZ) // 2
crop = inter[y0:y0 + _IMGSZ, x0:x0 + _IMGSZ]
rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)          # /255 + mean=0/std=1 与权重 transforms 一致，无需改动
x = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0).to(device)
```
同时**cam 必须按同一条几何链还原回原图**（不能直接 `resize` 到整图）：
```python
cam_crop = cv2.resize(cam, (_IMGSZ, _IMGSZ), interpolation=cv2.INTER_CUBIC)
cam_inter = np.zeros(inter.shape[:2], np.float32)
cam_inter[y0:y0 + _IMGSZ, x0:x0 + _IMGSZ] = cam_crop
cam = cv2.resize(cam_inter, (orig_w, orig_h), interpolation=cv2.INTER_CUBIC)
```
- **影响**：**会改变热力图形状**。当前 demo 图是正方形且主体居中 → 预期几乎无可见变化，但**必须人工目视复检**（`scripts/regenerate_heatmap.py` 可用来出对比图）。
- **回归**：`verify_pipeline.py` 只断言 `heatmap_url` 存在 → **5/5 通过**；若后续给脚本加"热力图像素级断言"，需在此修复后重新标定。
- **若时间紧张**：可延后（非崩溃项），但答辩前必须准备好口径——"识别视野（短边缩放+中心裁剪 224）与热力图坐标系是否一致"在当前实现下的诚实答案是**不一致**。

### FIX-9（P2）低风险加固（可批量做）

```python
# gradcam.py:242 前加一行
cam = np.clip(cam, 0.0, 1.0)         # INTER_CUBIC 过冲实测可达 1.09，np.uint8 会回绕成冷色
```
```python
# detector.py:162 简化（top5 实测恒为 min(5, nc)=5）
for i in range(3):
```
```python
# main.py 启动预热（消除 6.77s 冷启动）
@app.on_event("startup")
def _warmup():
    detector.load()
    detector.model.predict(np.zeros((224, 224, 3), np.uint8), verbose=False)  # 预跑一次，避免首次点击卡顿
```
- `_class_names`/`_disease_cn`（`detector.py:10-49`）确认死代码后可删；**但在删之前先跑 `scripts/verify_mapping.py` 确认 38/38 对齐**。
- `schemas/prescription_source`、`latency_ms` 等"展示用字段"建议一并加（前端报告 D.1 已提），后端约 8 行。

---

## 5. C. 面向验收的可核查结论

```
verdict: fail
```

**blocking**（仅限三类：正确性缺陷 / 需求未满足 / 契约安全数据完整性破坏）

```
blocking:
  - 违反项: 正确性缺陷 —— 声明的"降级回退"实为联网下载 + 必然 AttributeError
    证据: backend/app/config.py:11 (FALLBACK_MODEL = "yolo11n.pt"，相对名且是检测模型);
          backend/app/detector.py:126-128 (YOLO(FALLBACK_MODEL) 相对名触发联网下载);
          backend/app/detector.py:131-132 (无条件 children()[-1].conv.register_forward_hook);
          实测: models/ 目录仅含 best.pt / best_old.pt / yolo11n-cls.pt，yolo11n.pt 不存在;
                models/yolo11n-cls.pt（正确分类兜底）就在同目录未被引用;
          README.md:37 承诺与之相反（"未放置 best.pt 时会加载通用预训练权重"）
    期望: FALLBACK_MODEL 改为 MODELS_DIR / "yolo11n-cls.pt"；load() 增加 _resolve_head() 结构断言
          （末层必须含 conv/linear/pool），不匹配时给出明确中文报错；
          best.pt 缺失时必须真正降级而非崩溃/联网。

  - 违反项: 正确性缺陷 —— async 路由内全程同步阻塞 + 单例共享可变状态竞态
    证据: backend/app/main.py:42-94 (async def predict 内 shutil/OpenCV/YOLO/gradcam/requests 全同步);
          backend/app/prescriber.py:43-48 (requests timeout=30，无 connect/read 分离);
          backend/app/detector.py:111,138-142 (_penultimate_features 为 hook 写入的实例可变状态);
          backend/app/gradcam.py:168-170,253-254 (全局改 requires_grad 再恢复);
          backend/app/gradcam.py:176-186 (向共享模型注册 forward hook);
          实测: 冷启动首个 /predict 6.77s，暖态 0.10s；timeout=3 的黑洞请求实测 3.02s（线性外推 30s）
    期望: main.py 改 def predict 走线程池；detector 改为每次调用注册局部 hook 并 finally remove
          （消除共享状态）；detect+gradcam 由单一 threading.Lock 串行；LLM 调用置于锁外。

  - 违反项: 契约安全/数据完整性 —— 上传无类型白名单，任意内容落盘并被同源以 text/html 提供
    证据: backend/app/main.py:44 (后缀取自用户文件名，无白名单/无体积上限);
          backend/app/main.py:29 (app.mount("/uploads", StaticFiles(...))，无鉴权);
          实测: 上传 poc.html → 200 且落盘 uploads/d6c943203eb54e579bd6736148f13a9d.html(74B);
                GET /uploads/<该文件> → 200, content-type: text/html; charset=utf-8, 脚本原样返回;
                被 OOD 拒绝的 12MP 照片同样留在 uploads/；uploads 264 → 266 文件，只增不减
    期望: 扩展名白名单（显式排除 .svg/.html）+ 体积上限 + 原图用后即删/定期清理；
          热力图与原图分离目录，仅挂载热力图目录。

  - 违反项: 契约破坏 —— 无全局异常处理器，错误响应不是 PredictResponse 形状
    证据:           backend/app/main.py（全文无 try/except、无 @app.exception_handler）;
          backend/app/main.py:47-59（copyfileobj / precheck / detect 任一抛出即冒泡为未处理异常 → 500）;
          实测: 文件名 "a.jpg/../../x" → HTTP 500，响应体为纯文本 "Internal Server Error";
                缺 file 字段 → HTTP 422，响应体 {"detail":[...]};
          frontend/app.js:82 (r.json() 对纯文本抛 SyntaxError) 与 app.js:157 (data.detections.forEach)
          → 422 响应进入「成功分支」后崩溃，结果区留下空白卡片 + 英文报错
    期望: 注册 Exception 级异常处理器，返回 {"ok":false,"reason":"中文原因","detections":[],...}
          同形状；可预期的上传错误在端点内转成 ok=false。

  - 违反项: 需求未满足 —— 对外宣称的"大模型个性化处方"实际全程走死模板且无来源标识；
            且 .env 解析对四种常见写法静默失效
    证据: backend/app/config.py:21 (LLM_API_KEY 默认空，.env 实测不存在);
          backend/app/config.py:13-19 (手写解析，read_text("utf-8") 不剥 BOM);
          backend/app/prescriber.py:20-22 (无 key 直接走模板);
          backend/app/prescriber.py:51-52 (except Exception 静默回退，无日志/无标识);
          backend/app/schemas.py:12-18 (Prescription 无 source 字段);
          实测: .env 的 utf8_bom / export 前缀 / 引号包裹 / 行尾注释 四种写法全部静默失效，
                写错时 LLM_API_KEY 为空、系统静默走模板；
                .env.example 的占位 key "sk-your-key-here" 判真 → 每次请求 +1.026s 后仍静默回落模板
    期望: 改用 python-dotenv(encoding="utf-8-sig")；启动期对占位/畸形值 warning 或报错；
          响应增加 prescription_source("llm"/"template")；演示前配置真实 key 并端到端留证。
```

**advisory**

```
advisory:
  - 建议项: 依赖锁定与 setup 对齐
    理由: requirements.txt:8 ultralytics>=8.2 未锁定（8.4.153 已知与 forward hook 冲突，实测可用 8.4.137），
          且清单内完全没有 torch/torchvision；opencv/numpy 无上限；setup.bat:18 装 cu121 与实际 cu126 漂移；
          python-dotenv 已装却未列入。换机重装即可能不可复现，直接冲击"技术方案/佐证真实"。
  - 建议项: Grad-CAM 几何对齐（识别走短边缩放+中心裁剪，可视化走直接拉伸 640 并叠加整图）
    理由: 实测权重内置 transforms = Resize(224 短边)+CenterCrop(224)+Normalize(mean=0,std=1)；
          gradcam.py:161 无保持宽高比、无中心裁剪，二者在非正方形照片上不是同一视野。
          当前 demo 图是 256×256 正方形，两条路径恰好等价——这是缺陷未被发现的直接原因。
          注：这是"被追问即失分"的技术点，非崩溃项，可排在最后做，但需准备口径。
  - 建议项: 如实描述热力图的两通道贡献比例
    理由: 实测最终着色 5505 px 中 5318 px（96.6%）来自色温异常通道，Grad-CAM 本体仅约 220 px（4.0%）；
          _ANOMALY_HEAT 固定 0.85 也使异常区无法表达严重度。
          对外若强调"Grad-CAM++ 定位病灶"，与成图来源不符。
  - 建议项: 消除静默吞错并补齐日志
    理由: gradcam.py:255 / prescriber.py:51 的 except Exception 无日志；全仓无 logging 配置；
          "热力图没了"与"模型没认出"在日志上不可区分，现场故障无可查证据。
  - 建议项: 消除 import 期副作用；删除死代码
    理由: config.py:27-28 import 即 mkdir（DATA_DIR 全仓仅 config.py 引用，实际无人使用）；
          detector.py:10-49 的 _class_names/_disease_cn 为死代码（_CN_BY_NAME 已覆盖 38/38），
          且其 ___ 分支的 key 与真实类名前缀不符（"Corn" vs "Corn_(maize)"），一旦触发会回落英文；
          gradcam.py:221-225 为死存储（实测两次 Otsu 阈值 0.3047 vs 0.4141 证明第 239 行覆盖第 225 行）。
  - 建议项: OOD 分数对外措辞改为"启发式分布相似度"
    理由: 实测 ood_score 与 logits/softmax 量纲无关（合规图 0.3691 vs logit 24.3 / softmax 0.9955）；
          bias 存在（max|b|=1.3018）且忽略后 38 类排序改变；0.25/0.32 为经验阈值。
          已知假阴性有记录：2026-09-01.md:62 枫叶 0.33 越过 0.32 被判"正常"并识别为番茄·斑枯病。
  - 建议项: 补充回归用例（3 条即可闭合主要风险）
    理由: verify_pipeline.py 未覆盖 非图片文件 / 畸形文件名（500 路径）/ heatmap_url 指向文件是否存在 /
          上传类型与体积拒绝 / 并发。建议加"上传 txt 应 ok=false"、"畸形文件名应返回 JSON 而非 500"、
          "heatmap_url 指向的文件必须存在"。
  - 建议项: 修正文档的性能口径
    理由: 交接文档 7.6/7.7 的"单张热力图 0.10s/0.11s 对前端体验无影响"仅在 256×256 素材上成立；
          实测 12MP 手机照片下 generate_cam = 1.573s（慢 49 倍）、precheck 0.312s，端到端约 2.1s。
          建议补测条件，避免评委按真实手机照片追问时口径对不上。
  - 建议项: 版本控制与证据留存
    理由: 全仓无 .git；.gitignore:21 忽略 runs/，而 runs/agriguard_v2/results.csv 与 confusion_matrix*.png
          正是参赛证据。建议 git init + baseline，并把 .gitignore 改为 runs/**/weights/ 以保留 csv/png。
  - 建议项: CORS 收敛 / /docs 保留
    理由: 实测 Origin: https://evil.example 预检返回 access-control-allow-origin: *，
          任意网页可在受害者浏览器里驱动本机无鉴权推理（并读取结果）。
          建议 allow_origins 收敛到 ["http://127.0.0.1:8000", ...环境变量]；
          /docs 建议保留（讲解用），与收敛 CORS 不冲突。
```

**evidence**

```
evidence:
  - artifact_ref: backend/app/main.py            line: 42-94      说明: async 全同步 /predict 编排；无 try/except、无异常处理器
  - artifact_ref: backend/app/main.py            line: 44-47      说明: 后缀取自用户文件名、无白名单/体积上限、无清理
  - artifact_ref: backend/app/main.py            line: 29         说明: /uploads 静态挂载（无鉴权，长期公开）
  - artifact_ref: backend/app/main.py            line: 18-23      说明: CORS allow_origins/methods/headers 全为 *
  - artifact_ref: backend/app/main.py            line: 25-26      说明: detector/prescriber 模块级单例（惰性加载）
  - artifact_ref: backend/app/config.py          line: 11         说明: FALLBACK_MODEL 为检测模型且非本地路径
  - artifact_ref: backend/app/config.py          line: 13-19      说明: 手写 .env 解析（实测 4 类写法静默失效）
  - artifact_ref: backend/app/config.py          line: 21         说明: LLM_API_KEY 默认空 → 直接走模板
  - artifact_ref: backend/app/config.py          line: 27-28      说明: import 期 mkdir 副作用（DATA_DIR 无人使用）
  - artifact_ref: backend/app/detector.py        line: 124-136    说明: load() 无条件 hook 分类头，无结构断言
  - artifact_ref: backend/app/detector.py        line: 111,138-142 说明: _penultimate_features 共享可变状态
  - artifact_ref: backend/app/detector.py        line: 158,162    说明: conf=0.25（分类任务 no-op）、min(3,len(top5)) 无效保护
  - artifact_ref: backend/app/detector.py        line: 10-49      说明: _class_names/_disease_cn 死代码 + 前缀格式不符的潜伏陷阱
  - artifact_ref: backend/app/detector.py        line: 144-153    说明: _ood_score 忽略 linear.bias（实测 bias 存在且影响排序）
  - artifact_ref: backend/app/gradcam.py         line: 161,172    说明: 直接拉伸 640 无中心裁剪，与权重内置 transforms 几何不一致
  - artifact_ref: backend/app/gradcam.py         line: 168-170,253-254 说明: requires_grad 全局切换（并发不安全）
  - artifact_ref: backend/app/gradcam.py         line: 221-225    说明: heat_color/thr 第一次计算为死存储（实测两次阈值 0.3047/0.4141）
  - artifact_ref: backend/app/gradcam.py         line: 233,239    说明: 异常区抬升到 0.85 并重算 Otsu（副作用：挤掉 58px 弱病灶）
  - artifact_ref: backend/app/gradcam.py         line: 242        说明: np.uint8(255*cam) 未 clip，过冲 >1 会回绕成冷色
  - artifact_ref: backend/app/gradcam.py         line: 255-256    说明: except Exception 静默返回 None
  - artifact_ref: backend/app/prescriber.py      line: 20-22,43-52 说明: 无 key 走模板；timeout=30 不分离；except 静默吞错
  - artifact_ref: backend/app/schemas.py         line: 12-18,21-31 说明: Prescription 无 source 字段；PredictResponse 无 latency/severity
  - artifact_ref: frontend/app.js                line: 82,157     说明: r.json() 对非 JSON 错误响应抛错；detections.forEach 无兜底
  - artifact_ref: requirements.txt               line: 8          说明: ultralytics 未锁定、缺 torch/torchvision
  - artifact_ref: setup.bat                       line: 18         说明: cu121 与实际 cu126 漂移
  - artifact_ref: .env.example                    line: 5          说明: 占位 key 判真 → 每次请求多打一次注定失败的 HTTPS
  - artifact_ref: README.md                       line: 37         说明: "未放置 best.pt 会加载通用预训练权重" 与实现相反
  - artifact_ref: scripts/verify_pipeline.py      line: 61-123     说明: 5 项回归覆盖缺口（非图片/畸形名/热力图存在性/体积/并发）
  - artifact_ref: 开发交接文档.md                  line: 282,327    说明: "单张热力图 0.10s/0.11s" 仅对 256×256 素材成立
  - artifact_ref: .workbuddy/memory/2026-09-01.md line: 62         说明: 枫叶 ood 0.33 越过 0.32 阈值被放行（OOD 门已记录在案的假阴性）
  - artifact_ref: .venv/site-packages/ultralytics/data/augment.py      line: 24-25     说明: DEFAULT_MEAN/STD=(0,0,0)/(1,1,1) → "缺 ImageNet 归一化"否证依据
  - artifact_ref: .venv/site-packages/ultralytics/models/yolo/classify/predict.py line: 53-70 说明: 推理沿用权重内置 transforms（短边 Resize + CenterCrop）
  - artifact_ref: .venv/site-packages/starlette/formparsers.py         line: 183,230   说明: 1MB 限制只作用于非文件字段；文件溢写磁盘
  - artifact_ref: .venv/site-packages/ultralytics/engine/results.py    line: 1368-1379 说明: top5 恒为 list[:5]（取 Top3 正确）
  - artifact_ref: .venv/site-packages/ultralytics/utils/patches.py     line: 36-48     说明: detector 路径用 imdecode（实测与 imread 方向一致 → EXIF 担忧否证）
```

---

## 6. D. 复现方法（每条结论都可自行核对）

1. **结构与环境**（1 分钟）
   `.venv\Scripts\python.exe -B -c "import torch,ultralytics,cv2;print(torch.__version__,ultralytics.__version__,cv2.__version__)"`
2. **权重实测**：加载 `models/best.pt`，打印 `model.model.model[-1].__class__.__name__`、`.linear.weight.shape`、`.linear.bias is not None`、`model.model.transforms`（本篇 D3 段即由此得出"无 ImageNet 归一化"的否证）。
3. **`.env` 解析复核**：对同一段解析代码喂入带 BOM / `export ` / 引号 / 行尾注释的文本，打印得到的键名与值（本篇 1 节表格可直接复现）。
4. **500 与 422 契约复核（无需 GPU）**：
   `curl -F "file=@x.jpg;filename=a.jpg/../../x" http://127.0.0.1:8000/predict` → 观察 500 与响应体；`curl -X POST http://127.0.0.1:8000/predict -d x=1` → 观察 422。
5. **存储型 XSS 复核**：上传任意 `poc.html`，在 `uploads/` 目录里找到新文件，浏览器直接打开 `http://127.0.0.1:8000/uploads/<文件名>`。
6. **冷启动计时复核**：重启服务，第一次 `/predict` 计时（预期 5～7s），第二次（预期 0.1s 量级）。
7. **Grad-CAM 数值复核**：复算 cam → 打印 `cam.max()`、`(cam>1).sum()`、两次 `_otsu_threshold` 的返回值、两次 `heat_color` 的像素数（本篇 3 节数值：0.9986 / 0 / 0.3047 / 0.4141 / 278 / 5505）。
8. **回归基线**：任何修复后必跑 `.venv\Scripts\python.exe scripts\verify_pipeline.py`，要求 **5/5**。

---

## 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-09-20 | 首次生成 | 后端深度审查：7 个源文件逐行 + 依赖库契约核对 + 真机实测 + 真实 HTTP 复现 |
