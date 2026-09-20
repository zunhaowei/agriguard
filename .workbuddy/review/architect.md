# 禾目 AgriGuard 架构审查与国奖技术方案强化建议

- 审查人：高见远（首席架构师）
- 日期：2026-09-20
- 范围：`D:\shuangti11\ICAN\ican\CNDS`（全量源码 + 文档 + 日志）
- 性质：**存量项目审查（只读）**——本次未改动任何项目代码，仅产出本文件
- 前置事实：项目总监已确认的 11 条硬事实**直接采信不再重复发现**，本文件在其上深化

---

## 0. 结论速览

1. **一句话定性**：算法层是真资产，工程层是欠债区。
   - 算法层（OOD 双阈值、Grad-CAM++、色温异常通道）三者互不重复、各有实测标定依据，是竞品没有的差异化内核，**不要动其阈值与逻辑**。
   - 工程层（并发、配置、契约、卫生）问题密集，但大多是**低风险可渐进修复**的欠债，不是重写理由。
2. **国奖胜负手不在"功能数量"**，在两点：把算法洞见讲成**可追溯的研发故事**（原创性 20）、让**现场演示永不翻车**（巡展现场演示 50%）。堆 Vue+MySQL+环境监测是对标竞品的同质化，不推荐。
3. **最高 ROI 的 3 个技术增强项**（均不触碰模型重训、复用现有代码）：严重度量化闭环、反馈-增学闭环、拍摄引导。详见 B.1。
4. **5 条 blocking**：2 条正确性缺陷（fallback 崩溃、并发阻塞+竞态）、1 条需求未满足（大模型处方实为死模板）、2 条契约安全（CORS+上传无校验、进度面板暴露 `.env`）。详见 C。

---

## A. 架构审查

### A.1 分层与耦合现状评估

**现状：`backend/app/` 平铺式 7 文件，职责可行但无层次。**

| 文件 | 行数 | 实际承担 | 问题 |
|---|---|---|---|
| `main.py` | 94 | 入口 + CORS + 静态挂载 + `/predict` **编排** | 路由与业务编排混在一个函数；无分层 |
| `config.py` | 29 | 路径常量 + **手写 .env 解析** + LLM 配置 + **import 期 mkdir** | import 有副作用；python-dotenv 已装却未用 |
| `schemas.py` | 31 | Pydantic 模型 | 无问题 |
| `detector.py` | 186 | YOLO 推理 + 中英映射 + OOD 打分 + **模块级单例 + 可变实例状态** | 见 A.3 / A.4 |
| `precheck.py` | 173 | 形式校验 + 前景掩膜 | 无问题（算法好） |
| `gradcam.py` | 256 | Grad-CAM++ + 色温通道 | 层索引硬绑定、静默吞错，见 A.4 |
| `prescriber.py` | 72 | LLM/模板处方 | 静默吞错掩盖配置缺失，见 A.4 |

**问题清单（按优先级）：**

1. **配置/推理/可视化/编排耦合**：`main.predict`（`main.py:43-94`）一个函数里串了落盘、precheck、detect、prescribe、gradcam 五步，业务无法被脚本或测试直接复用（现在测试只能走 HTTP）。
2. **`config.py` import 期副作用**：`config.py:13-19` import 即读 `.env` 并写 `os.environ`；`config.py:27-29` import 即 `mkdir` 三个目录。任何 `import app.config` 都会在磁盘上产生副作用，测试与工具链无法干净隔离。
3. **业务常量三处重复**：
   - 作物集合：`detector.py:10-25`（英文）、`main.py:66`（硬编码中文长串）、`frontend/index.html:43`（中文列表）。
   - OOD 阈值：`detector.py:121-122`（0.25/0.32） vs `frontend/app.js:103`（"拒识阈值 0.25"）、`app.js:146`（"≥0.32 为正常"）。**当前一律写死**，改后端漏改前端即导致 UI 文案骗人。
4. **无上传边界**：`main.py:44-47` 取用户后缀直接落盘、无体积/类型白名单、无清理。
5. **CORS 全开**：`main.py:18-23` `allow_origins=["*"]`、无鉴权、无限流。

### A.2 渐进式分层重构方案

**目标结构（不推倒重来，按文件搬迁）：**

```
backend/app/
  main.py                 # 只做装配：create_app() → 中间件/路由/静态/启动钩子
  core/
    config.py             # Settings：dotenv 显式加载，无 import 副作用
    constants.py          # 单点真相：SUPPORTED_CROP_CN / OOD 两阈值
  schemas/
    predict.py            # 现 schemas.py 内容
  api/
    routes_predict.py     # APIRouter(prefix="/api/v1")，只做 HTTP 边界
    routes_meta.py        # GET /meta：返回阈值+作物列表（前端不再硬编码）
  services/
    diagnosis.py          # 编排（从 main.predict 抽出，纯业务）
    detector.py  precheck.py  gradcam.py  prescriber.py
  model_registry.py       # 单例装配 + 推理锁 + 结构内省 resolve_backbone()
```

**分步实施（每步独立提交、可 `git revert` 回滚）：**

- **Step 0（前置，零风险）版本控制**：在 `CNDS` 下 `git init`，首次提交当前状态为 `baseline`。
  - **为什么**：无 `.git` 时"每步可回滚"是空话；这是所有后续步骤的**使能前置**。`.gitignore` 已忽略 `data/ uploads/ runs/ media/ .venv/ .env`，提交体积可控（源码 < 1 MB）。
- **Step 1 抽 `core/constants.py` 消除三处重复**：
  - 新增 `SUPPORTED_CROP_CN`（14 项）、`OOD_REJECT_THRESHOLD=0.25`、`OOD_WARN_THRESHOLD=0.32`。
  - `detector.py`：`__init__` 的两阈值字面量改为引用常量（保留实例属性，接口不变）。
  - `main.py:66`：硬编码作物串改为 `"、".join(constants.SUPPORTED_CROP_CN)`。
  - 新增 `GET /api/v1/meta`；`app.js:103,146` 与 `index.html:43` 改为从该端点取值。
  - **为什么**：消除"改一处漏两处"的漂移与 UI 谎报阈值。
- **Step 2 消除 `config.py` import 副作用**：
  - 用 `from dotenv import load_dotenv; load_dotenv(BASE_DIR/".env")` 替换手写解析（`config.py:13-19`）。
  - `mkdir`（`config.py:27-29`）移入 `ensure_dirs()`，由 `create_app()` 启动时调用。
- **Step 3 抽 `services/diagnosis.py`**：把 `main.py:43-94` 主体搬为 `def diagnose(image_path, filename) -> PredictResponse`；`main.predict` 瘦身为"落盘 → 调 diagnose"。**为什么**：路由只做 HTTP，业务可被脚本/测试直接调用。
- **Step 4 路由版本化**：`api/routes_predict.py` 用 `APIRouter(prefix="/api/v1")`；`main.py` 改 `include_router`。**保留旧 `/predict` 别名一个版本周期**，前端切 `/api/v1/predict`。
- **Step 5 schema 拆包**（可选）：`schemas/predict.py`。
- **迁移期兼容**：`app/schemas.py`、`app/detector.py` 等旧路径保留为**薄 re-export shim**，避免 `scripts/` 或外部调用断裂；全部切换后再删 shim。

> 硬约束：单文件 ≤ 300 行、单一职责、入口只装配、按资源分包。现状 `gradcam.py` 256 行已是上限，新增逻辑应下沉到独立模块而非继续膨胀。

### A.3 并发模型的正确修法

**病灶**：`main.py:42` 是 `async def predict`，但函数体内全程同步阻塞（`shutil.copyfileobj` 落盘、OpenCV、YOLO 推理、`requests.post` 30s 超时）。**事件循环被完全堵死**——一次 `/predict` 进行中，`/health`、静态文件、其它请求全部挂起；LLM 调用最坏 30s 内整个服务假死。

**三条路线对比：**

| 路线 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| ① 改 `def predict` | `async def` → `def`，FastAPI 自动丢 anyio 线程池（默认 40 线程） | 一行改动，事件循环立刻解放 | 暴露单例共享可变状态的竞态 |
| ② `run_in_threadpool` | 保留 async，对阻塞调用逐个包裹 | 粒度细 | 需穿线整条链，收益不如①，仍不解决竞态 |
| ③ 进程级模型服务 | 推理独立进程/微服务，队列或 HTTP 通信 | 真并行、事件循环完全隔离 | 多进程/端口/调度，2-5 人团队的**演示翻车面**显著增大 |

**选型结论：路线 ① + 粗粒度推理锁（`threading.Lock`）。**
理由：
- **正确性优先**：MVP 阶段 GPU 单卡本就是串行资源，把当前"靠事件循环阻塞意外串行化"（团队硬事实 5）变成**显式串行**，是诚实而非降级。
- **体验达标**：事件循环解放后，LLM 的 30s 网络等待不再阻塞其它请求与健康检查——这正是"现场演示效果 50%"的底线。
- **拒绝路线 ③**：演示型作品，每多一个进程/端口都是一个现场翻车点；进程隔离的收益（吞吐）在这个作品的使用场景里不存在。保留为"规模化的下一步"。

**竞态消除细则（要具体到锁粒度与状态归位）：**

- **锁边界**：只锁"模型状态临界区"——`detector.detect` + `generate_cam`。**LLM 处方（网络 I/O）放在锁外**，否则一次慢调用会拖住所有人的推理。
  ```python
  # services/diagnosis.py
  with _model_lock:                                  # 模型/GPU 临界区
      detections, ood, is_ood, is_warn = detector.detect(path)
      heatmap_url = _safe_cam(detector.model, path, detections[0].class_id, heat_path) \
                    if detections and detections[0].class_id is not None else None
  prescription = prescriber.generate(detections)      # 锁外：网络 I/O
  ```
- **状态归位（根因修复，优先于加锁）**：`Detector._penultimate_features`（`detector.py:111,142`）是 forward hook 写入的**实例级可变状态**。改为**每次调用注册局部 hook**（对齐 `gradcam.py:176-186` 已有的局部 `acts={}` 写法），用完即 `remove()`：
  ```python
  def detect(self, image_path):
      feats = {}
      classify = self._head
      h = classify.conv.register_forward_hook(
          lambda m, i, o: feats.update(v=classify.pool(o).view(-1).detach()))
      try:
          results = self.model.predict(image_path, conf=0.25, verbose=False)[0]
      finally:
          h.remove()
      ood_score = self._ood_from(feats.get("v"))     # 只读局部变量
  ```
  如此即便将来去掉锁，`detect` 也不再依赖共享状态。
- **`gradcam` 必须加锁（状态归位解决不了）**：`gradcam.py:168-170` 把参数 `requires_grad_(True)`、`gradcam.py:253-254` 再恢复，`gradcam.py:174-186` 注册到**共享模型**上的 forward hook。两个并发调用会交叉触发彼此的 hook、且一个线程恢复 `requires_grad` 时另一个还在反传——**这是全局状态竞争，只能靠锁串行**。
- **`model.eval()` / `requires_grad` 切换是全局的**：同样由 `_model_lock` 保护。
- **落盘与 cv2 无需加锁**：纯本地、无共享状态，可并行。

> 结论：`main.py:42` 改 `def predict`，`services/diagnosis.py` 用 `_model_lock` 包裹 detect+gradcam，`detector` 去掉实例可变状态。三者叠加后：事件循环不阻塞、GPU 串行正确、竞态消除。

### A.4 可维护性风险

1. **`gradcam.py` 层索引硬绑定（`gradcam.py:34-35` `_TARGET_LAYER=9` / `_HEAD_LAYER=10`）**
   - 绑定 `yolo11n-cls` 的 `nn.Sequential` 次序。换 backbone（nano→small）或升/降 ultralytics 版本，索引会**静默指向别的层**——不报错，但热力图语义全错。
   - **改法**：新增 `model_registry.resolve_backbone(model)` 做**结构内省**而非数索引——按类型找最后一个 4D 输出层（C2PSA）作为 target、按"含 `.linear` 属性"或 `isinstance(..., Classify)` 找 head；启动时断言通道数（256）与可解析性，**失败即快速报错**。

2. **两套不一致的索引约定**：`detector.py:131` 用 `list(self.model.model.model.children())[-1]`（取最后 child）；`gradcam.py:174-175` 用 `model.model[9]`（按整数索引）。同一 backbone 两种寻址方式，任一侧假设失效即分叉。且两者都依赖 `model.model.model` **三级属性链**，跨 ultralytics 版本脆弱。
   - **改法**：统一走 `resolve_backbone()` 单点解析，两个模块都从这里取 `(head, target_layer)`。
   - 附带：`detector.load()` 在**加载期**注册常驻 hook（`detector.py:132`），`gradcam` 在**调用期**注册临时 hook——同一模块上两套 hook 生命周期。`detector` 的常驻 hook 会在 gradcam 前向时触发并覆写 `_penultimate_features`（对 gradcam 无害，但暴露耦合）。随状态归位一并清理。

3. **静默吞错**：
   - `gradcam.py:255` `except Exception: return None` → `main.py:85` 视作"无热力图"，**无任何日志**。系统性失败（层不匹配、显存不足）在演示里表现为"功能悄悄没了"。
   - `prescriber.py:51` `except Exception: return self._generate_from_template(top)` → **掩盖 LLM 配置缺失**，使系统"看起来有大模型处方"实际是模板（这正是 blocking B3 的技术成因）。
   - **改法**：① 至少 `logging.exception`；② 区分预期异常（图片损坏）与非预期（梯度/显存）并上抛或落日志；③ 响应体新增 `prescription_source: "llm" | "template"`，让前端/答辩**诚实显示**实际路径。

### A.5 模型可信度核验（"坍缩"复核）——答辩杀伤力评估

- **背景**：`2026-09-01.md:60` 记录早前 32 张通过图中 **68.8% 被判「番茄·早疫病」**（top1 100%、top2≈0%）。v2 重训后 top1=99.7%，但**未用混淆矩阵复核**，是否真解决属未知。
- **答辩杀伤力：高。** 它是"代码看不出、但一复盘训练数据就暴露"的隐藏缺陷。若评委有 ML 背景，问一句"99.7% 是 top1，那**各类召回是否均衡、混淆矩阵长什么样**"，答不上来 → 技术方案 20 直接掉分；更严重的是，日志里**自己记了坍缩风险却没闭环验证**，反而把"可追溯"变成"发现了问题没解决"的证据。
- **核验方案（可执行）**：
  1. 读 `runs/agriguard_v2/confusion_matrix_normalized.png` 与 `results.csv`（已在仓库）。
  2. 新增只读脚本 `scripts/verify_confusion.py`：加载 `models/best.pt` 对 `data/plantvillage/val` 全量预测，输出 38×38 混淆矩阵 + 每类 precision/recall/F1，**重点打印 `Tomato___Early_blight` 的 recall 与误入该类的 top 来源分布**。
  3. **判据**：各类 recall 最低值 ≥ 0.90 且 `Tomato___Early_blight` recall ≥ 0.95 → 判定坍缩已解决，**把该实验作为"关键节点"写进研发过程时间线**（强化原创性）；否则列入风险并说明缓解。
- **叙事建议**：若核验通过，"曾坍缩 → 定位为数据不平衡+容量不足 → v2 强增强重训 → 混淆矩阵逐类复核达标"是一条**完整闭环**，比"一直很好"更有说服力。前提是**真的复核并留证**。

---

## B. 国奖技术方案强化建议

> 评判标准：能否让评委觉得"别人做不出来"、实现风险可控、区域赛前可完成。**明确不堆 Vue+MySQL+环境监测这类同质化"大而全"。**

### B.1 三个高 ROI 增强项

#### 增强项 1：病灶严重度量化（把"热力图"变成"数字 + 分级处方"）

- **对应评分项**：创新性 35（主）+ 技术方案 20；间接撑实用性 25。
- **加分逻辑**：竞品只有检测框，回答的是"**哪里**"；我们回答"**多严重**"。作品名里的"精准处方"，目前**没有任何量化支撑**——加上 `lesion_area_ratio` + `severity_grade` 后，"识别 → 定位 → **量化** → 分级用药"形成完整循证链，每一环都有数字。
- **实现路径**：
  1. `services/gradcam.py::generate_cam` 除 `out_path` 外返回 `stats`：前景内病灶像素占比（复用现有 `heat_color` mask，`gradcam.py:225/239`）、色温异常占比（`_color_anomaly_mask` 输出，`gradcam.py:230`）。
  2. `services/diagnosis.py` 聚合 → `severity_grade`（轻/中/重，按 `lesion_ratio` 阈值，需用仓库样例标定）；`schemas.PredictResponse` 增字段。
  3. `prescriber` prompt 注入 severity 与 ratio，**模板兜底也按分级给不同文本**（避免"分级了但处方不变"穿帮）。
  4. 前端加严重度条 + 病灶面积百分比。
- **工作量/风险**：0.5-1 人日。风险＝阈值标定偏主观——但只用于**分级展示**，不进入判识关键路径。
- **降级方案**：只展示 `lesion_ratio` 数字不做分级；或分级用粗阈值（<5%/5-20%/>20%）并在 UI 注明"估算值"。

#### 增强项 2：反馈-增学闭环（可追溯 + 数据飞轮）

- **对应评分项**：原创性 20（主）+ 创新性 35。
- **加分逻辑**：iCAN 明确要求"构思到成品**可追溯**、逻辑连贯、材料真实、**完整呈现研发过程与关键节点**"。静态日志是"过去时"；反馈闭环是"**现在进行时且现场可演示**"——评委当场纠正一次 → 落盘 → 展示"这条已进入下一轮训练队列"。竞品（单向识别）完全没有。
- **实现路径**：
  1. `POST /api/v1/feedback`（image_id + predicted + corrected + note），落盘 `feedback/*.json` + 图。
  2. 前端"结果不对？点此纠正"下拉（38 类）→ 提交。
  3. `scripts/finetune_feedback.py`：读 feedback，ultralytics 加载 `best.pt`，小 lr 微调（或仅训 head），产出候选权重 + loss 曲线。
  4. 可选 `GET /api/v1/feedback/summary` 展示累计纠错数。
- **工作量/风险**：端点+UI 1-1.5 人日，微调脚本 0.5 人日。风险＝需真实反馈才有说服力 → 演示前自造 10-20 条、跑一次微调展示 loss 下降即可。
- **降级方案**：只做"收集 + 展示 + 脚本存在"，不真训；口径为"已具备持续学习能力，现场演示收集环节"。

#### 增强项 3：拍摄引导（把"事后拒绝"变"过程引导"）

- **对应评分项**：实用性 25（主）+ 技术方案 20。
- **加分逻辑**：竞品假设"用户会选对作物"；我们假设"用户**不会拍**"——所以把 `precheck` 从"拒绝"升级为"**实时引导**"。这把一个高失败率的实验室工具变成能收敛野外输入的实用产品，并展示"我们清楚模型的适用边界"（技术洞见）。
- **实现路径**：
  1. 新增 `POST /api/v1/check`：复用 `precheck.check_leaf_and_background`，纯计算不落库，返回三项指标 + 逐项阈值 + 通过与否 + 人话建议（+ 可选前景掩膜可视化）。
  2. 前端上传前调用，实时展示"叶片占比/背景纯净度"进度条与针对性建议（换背景/靠近拍/补光）。
  3. 进阶（非必须）：把精简后的 precheck 放前端本地做实时。
- **工作量/风险**：0.5 人日，纯复用，低风险。
- **降级方案**：只做"上传后即时反馈 + 改进建议"，复用现有 precheck 结果，仅细化前端展示。

### B.2 竞品"9 个按作物分模型"的反制话术要点

竞品：Vue+SpringBoot+Flask+MySQL，YOLOv11 **检测**，按作物拆成 9 个独立模型（含水稻/小麦/棉花/玉米）。**反制不能被"模型更多=更专业"带节奏**，按五层拆：

1. **用户体验（决定性）**："分模型要求用户**先知道这是什么作物**——这恰是农业新手最不知道的事。让用户先做一次作物识别再走病害识别，等于把系统的核心难点推回用户。我们单模型直接输出「番茄·早疫病」，**零前置知识、一步到位**。"
2. **技术洞见**："38 类单模型迫使模型学习**跨作物共享的统一病征表征**（叶斑/霉层/锈斑/黄化在同一特征空间判别）；分模型是 9 个小专家，表征无法共享、样本被切碎，小样本作物更易过拟合。我们 1.58M 参数覆盖 38 类，**参数效率更高**。"
3. **工程与演示**："分模型＝9 份权重、9 套类名映射、9 条推理分支、9 份版本管理；我们＝1 份 3.28MB 权重、一次前向、**毫秒级**。'更专业'是以**更多工程负担**换来的，不是技术优越。"
4. **可解释性（对方硬伤）**："他们是检测（框），给不出病灶在哪、多严重；我们有 Grad-CAM++ 病灶定位 + 色温异常通道 + 严重度量化——**从'框'到'定位+量化'**。评委问'为什么是这个病'，我们能指热力图；他们只能给一个框。"
5. **边界诚实**："我们有 OOD 拒识——**知道自己不知道**；9 个检测模型对训练外作物是否也过度自信？未见拒识机制。**敢拒识**比'永远给答案'更专业。"
- **一句话总括**："分模型解决的是'把大问题切成小问题'的**工程便利**；我们解决的是'用户不必先成为植物学家'的**产品问题**，以及他们没碰的**可信问题**。"（并补一句：单模型是 MVP 最优形态，架构上已为后续多模型路由预留。）

### B.3 中国本土主粮缺失（水稻/小麦/棉花）评估

- **事实**：PlantVillage 本身**不含**水稻/小麦/棉花（欧美作物数据集）。竞品的本土主粮来自其它数据源，是其"实用性"卖点。iCAN 是中国赛事，对中国评委来说这是**情感+国情刚需**，缺失会在实用性 25 被直接对比。
- **是否值得补：有条件补，且用最小代价；否则不硬塞。**
- **最小可行路径（若补）**：
  1. **数据来源**（本环境实测可达，按可行性排序）：魔搭 ModelScope `rice/wheat/cotton leaf disease`；天池农业数据集。**找不到干净标注就不补**。
  2. **关键架构约束**：**不要**把 3 个新作物塞进同一分类头重训 41+ 类——会打乱现有 38 类的 OOD 权重标定（`detector.py:135-136` 的 `_class_weights_norm`），且小样本新类拉低整体。**更稳做法**：主模型不动，新增"本土作物扩展包"（第二分类头/第二模型），在 `diagnosis` 层做路由。
  3. **训练成本**（实测口径）：nano @224 每轮 ~77s，30 轮 ~40 分钟；数据整理 ~1-2 小时（磁盘 IO 慢是已知坑）→ **数据现成时 1 天内可完成**。
- **风险**：数据质量差 → 引入噪声、答不上"你的水稻数据哪来的、标注可靠吗"，**比不覆盖更伤**（动摇原件真实性）。
- **若不补（保守方案）——答辩应对**：
  1. **诚实边界 + 战略清晰**："我们覆盖 PlantVillage 38 类（14 种作物），这是国际公认基准；本土主粮涉及更复杂的田间场景与地域病征差异，我们选择先把'**单模型零前置 + 可解释 + 敢拒识**'做深做透，而非用来源不明的数据堆作物数——**覆盖面不等于诊断可信度**。"
  2. **短板转洞见**：现场**故意**上传一张水稻叶，展示系统**诚实拒识**——用 OOD 证明我们有边界意识，比"什么都敢答"更专业。
  3. **给 roadmap**："本土主粮是既定扩展方向，架构上 `detector` 已为多模型路由预留。"——把缺失变成"有规划的下一步"。
- **结论**：区域赛前若有 ≥2 天缓冲且能在魔搭/天池找到**干净标注**的水稻/小麦数据 → 补（独立扩展包，不混主模型）；否则**不补**，走"诚实边界 + 边界意识演示 + roadmap"。**优先级低于 B.1 三项。**

---

## C. 面向验收的可核查结论

```
verdict: fail
```

**blocking**（仅限：正确性缺陷 / 需求未满足 / 契约安全数据完整性破坏）

```
blocking:
  - 违反项: 正确性缺陷 —— 声明的"降级回退"实为启动即崩
    证据: backend/app/config.py:11 (FALLBACK_MODEL = "yolo11n.pt" 是检测模型);
          backend/app/detector.py:124-132 (load() 无条件 list(model.model.model.children())[-1].conv.register_forward_hook)
    期望: FALLBACK_MODEL 指向同目录已存在的分类权重 models/yolo11n-cls.pt，
          或用 resolve_backbone() 做类型断言并在不匹配时给出清晰报错；
          models/best.pt 缺失时应真正降级而非崩溃。

  - 违反项: 正确性缺陷 —— async 路由内全程同步阻塞 + 单例共享可变状态竞态
    证据: backend/app/main.py:42-94 (async def predict 内 shutil/OpenCV/YOLO/requests 全同步，
          requests timeout=30 会堵死事件循环);
          backend/app/detector.py:111,138-142 (_penultimate_features 为 hook 写入的实例可变状态);
          backend/app/gradcam.py:168-170,253-254 (临时改 requires_grad 再恢复);
          backend/app/gradcam.py:174-186 (向共享模型注册 forward hook)
    期望: main.py 改 def predict 走线程池；detector 改为每次调用注册局部 hook 消除共享状态；
          gradcam 与 detect 由单一 _model_lock 串行；LLM 调用置于锁外。

  - 违反项: 需求未满足 —— 对外宣称的"大模型个性化处方"实际走死模板且无来源标识
    证据: backend/app/config.py:21 (LLM_API_KEY 默认空，.env 实测不存在);
          backend/app/prescriber.py:20-22 (无 key 走 _generate_from_template);
          README.md:39-47 与 docs/产品介绍文案.md 均以"大模型处方"为核心卖点
    期望: 响应体暴露 prescription_source("llm"/"template")；
          演示/参赛前必须配置真实 .env 并端到端验证；文案与真实行为一致。

  - 违反项: 契约安全 —— 无上传边界 + CORS 全开 + 上传永不清理
    证据: backend/app/main.py:18-23 (allow_origins=["*"]);
          backend/app/main.py:44-47 (后缀取自用户文件名、无体积/类型白名单、无清理);
          uploads/ 实测 259 文件 / 11.5MB 只增不删
    期望: 上传类型白名单 + 体积上限 + 定期清理策略；CORS 收敛到演示所需来源。

  - 违反项: 契约安全 —— 进度面板脚本以 http.server 托管项目根，可 HTTP 读取 .env
    证据: serve_panel.bat:6 (".venv\Scripts\python.exe" -m http.server 8001 --bind 127.0.0.1，
          工作目录为项目根)
    期望: 删除该脚本，或将其托管目录限定到不含 .env 的独立子目录；
          二者须与 B3 修复（新增 .env）同步执行——否则修复 B3 会激活本条。
```

**advisory**

```
advisory:
  - 建议项: 建立版本控制（git init + baseline 提交）
    理由: 无 .git 时"渐进重构、每步可回滚"无法兑现，是所有重构步骤的使能前置。
  - 建议项: 层索引解耦与索引约定统一
    理由: gradcam.py:34-35 的 _TARGET_LAYER=9/_HEAD_LAYER=10 与 detector.py:131 的
          children()[-1] 是两套寻址；换模型/升级 ultralytics 会静默错位。建议统一 resolve_backbone()。
  - 建议项: 消除静默吞错
    理由: gradcam.py:255 / prescriber.py:51 的 except Exception 无日志，掩盖配置缺失与系统性失败。
  - 建议项: 依赖锁定与 setup 对齐
    理由: requirements.txt:8 ultralytics>=8.2 未锁定（8.4.153 有已知崩溃坑），且缺 torch/torchvision；
          setup.bat:18 装 cu121 与实测 cu126 漂移。
  - 建议项: 用混淆矩阵复核"坍缩"，并留证
    理由: 见 A.5；历史 68.8% 单类坍缩未闭环验证，是答辩隐藏扣分点，核验通过反而强化原创性叙事。
  - 建议项: 前端 emoji 图标替换为 SVG
    理由: frontend/index.html:12 以 emoji 作功能徽标，违反团队 P0"禁止 emoji 作功能图标"；
          应改用 assets/logo_icon.svg。
  - 建议项: 修复前端对象 URL 泄漏
    理由: frontend/app.js:70 每次上传 createObjectURL 未 revoke。
  - 建议项: 仓库卫生与孤儿清理
    理由: 约 7.2GB 可回收；12 个素材脚本产物缺失成孤儿；根目录残留废弃产物。
  - 建议项: 研发过程时间线材料化
    理由: 原创性 20 的最高杠杆是"构思→成品"的可追溯叙事；建议把 4 篇日志 + 交接文档 + 关键节点
          （坍缩定位/v2 重训/热力图三代迭代）整理为一条时间线，作为答辩主线索（非代码动作）。
```

**evidence**

```
evidence:
  - artifact_ref: backend/app/main.py            line: 42-94     说明: /predict 编排 + async 阻塞 + 无上传边界
  - artifact_ref: backend/app/main.py            line: 18-23     说明: CORS allow_origins=["*"]
  - artifact_ref: backend/app/main.py            line: 66        说明: 支持作物清单硬编码（重复来源之一）
  - artifact_ref: backend/app/config.py          line: 11        说明: FALLBACK_MODEL 为检测模型
  - artifact_ref: backend/app/config.py          line: 13-19,27-29 说明: import 期读 .env + mkdir 副作用
  - artifact_ref: backend/app/config.py          line: 21        说明: LLM_API_KEY 默认空
  - artifact_ref: backend/app/detector.py        line: 131-132   说明: children()[-1] + 常驻 forward hook
  - artifact_ref: backend/app/detector.py        line: 111,138-142 说明: _penultimate_features 共享可变状态
  - artifact_ref: backend/app/detector.py        line: 121-122   说明: OOD 阈值 0.25/0.32（真值来源）
  - artifact_ref: backend/app/gradcam.py         line: 34-35     说明: 层索引硬绑定
  - artifact_ref: backend/app/gradcam.py         line: 168-170,253-254 说明: requires_grad 全局切换
  - artifact_ref: backend/app/gradcam.py         line: 255       说明: except Exception 静默返回 None
  - artifact_ref: backend/app/prescriber.py      line: 20-22,51  说明: 模板兜底 + 静默吞错
  - artifact_ref: backend/app/schemas.py         line: 21-31     说明: PredictResponse 缺 prescription_source/severity
  - artifact_ref: frontend/app.js                line: 103,146   说明: 阈值 0.25/0.32 前端硬编码
  - artifact_ref: frontend/app.js                line: 70        说明: createObjectURL 未 revoke
  - artifact_ref: frontend/index.html            line: 43        说明: 作物清单前端硬编码
  - artifact_ref: frontend/index.html            line: 12        说明: emoji 功能徽标（P0 违规）
  - artifact_ref: requirements.txt               line: 8         说明: ultralytics 未锁版本、缺 torch
  - artifact_ref: setup.bat                       line: 18        说明: cu121 与实际 cu126 漂移
  - artifact_ref: serve_panel.bat                 line: 6         说明: http.server 托管项目根
  - artifact_ref: .workbuddy/memory/2026-09-01.md line: 60       说明: 68.8% 坍缩记录（未闭环验证）
```

---

## 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-09-20 | 首次生成 | 架构审查 + 国奖技术方案强化建议 |
