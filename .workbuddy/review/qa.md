# QA 验收与质量核验报告 — 禾目 AgriGuard

- 核验人：严过关（测试工程师）
- 核验日期：2026-09-20
- 项目根：`D:\shuangti11\ICAN\ican\CNDS`
- 环境实况：base Python 3.13.12 + venv site-packages（`.venv\Scripts\python.exe` 的 `pyvenv.cfg` **home 指向已不存在的 `C:\Users\19057\...`，venv 的 python.exe 直接不可用**；本次改用 base 解释器 + `PYTHONPATH=<venv site-packages>` 运行，torch 2.13.0+cu126 / CUDA 可用）。bash 已损坏，全部经 PowerShell 重定向落盘后用 Read 读取。
- ⚠️ **重要前提**：核验过程中后端正被队友**并发重构**（`backend/app/` 8 个文件时间戳集中在 2026-09-20 14:46–14:49，新增 `constants.py`/`imaging.py`/`model_arch.py`）。本报告的"当前状态"结论均以 **14:49:53 之后的代码 + 重启后的服务** 为准，并已重新拉取文件快照。

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| **模型"坍缩"** | ✅ **已解决**（机器实测：38/38 类被正确区分，预测分布熵 5.2472/5.2479，番茄·早疫病仅占 2.6%） |
| 现状模型是否可信 | 在 **训练同分布（PlantVillage 式）** 上可信；田间实景鲁棒性未验证 |
| 回归基线 | ❌ 不通过（`verify_pipeline.py` 4/5） |
| 安全边界 | ✅ 已修复（.html/文本/超大/过小/白图全部被正确拒收） |
| 视觉合规 | ❌ 前端仍有 1 处 emoji 图标 |
| 数据/证据完整性 | ✅ 数据、哈希、映射均真实自洽；但**训练产物溯源与文档口径不一致** |
| 生产就绪档位 | **Bronze**（未达 Silver，见 §7） |
| verdict | **fail**（见 §8） |

---

## 1. 模型"坍缩"独立复核（最高优先级）

**问题回顾**：`memory/2026-09-01.md` 记录旧模型 32 张通过图 68.8% 被判为「番茄·早疫病」（top1≈100%、top2≈0%），归因"数据不平衡 + 容量过小"。09-15 重训 v2 报 top1=99.7%。99.7% 本身既可能是真准，也可能是"退化成只输出多数类"的假象，必须独立验证。

**方法**：对 `data/plantvillage/val` 的 **38 类各抽 10 张（共 380 张）**，走真实生产路径 `Detector.detect()`（脚本 `_tmp_model_check.py`，输出 `_tmp_model_check_out.txt` / `.json`）。

### 1.1 关键数字（机器证据）

| 指标 | 实测值 | 判读 |
|---|---|---|
| 整体 top1 准确率 | **378/380 = 99.47%** | 与 results.csv 的 99.74% 同量级，非单类坍缩可以伪造 |
| **被预测出的类别数** | **38 / 38** | 坍缩模型只能输出 1 类；此处 38 类全出现 |
| **预测为「番茄·早疫病」** | **10/380 = 2.6%**（旧模型 68.8%） | 坍缩症状消失 |
| **预测分布香农熵** | **5.2472 bits / 最大 5.2479** | 近乎均匀，与"每类等量抽样"的期望一致 |
| 每类准确率 | 36/38 类 **10/10**，其余 2 类 9/10 | 仅 2 张错判且都是"近邻类混淆" |
| top1–top2 置信度差 | 均值 0.9910 | 高置信且与次类分离明显 |
| ood_score（同分布） | 均值 **0.5122**，min 0.2375 | 378/380 ≥0.32（正常区） |

**仅有的 2 例错判**（属合理近邻混淆，非坍缩）：
- `Cherry_(including_sour)___healthy` → `Raspberry___healthy`（conf 0.69，ood 0.2375）
- `Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot` → `Corn_(maize)___Northern_Leaf_Blight`（conf 0.78）

### 1.2 混淆矩阵交叉验证

`runs/agriguard_v2/confusion_matrix.png`（Read 查看）：**对角线干净、无任何一行被压到单一列**；深色块对应 Orange 黄龙病(1101)/Soybean 健康(1018)/Tomato YLCV(1071) 等大类，是样本量差异而非坍缩。

### 1.3 结论

> **坍缩已解决。** 部署权重 `models/best.pt` 在 38 类上均具备真实判别力，**不是**"总是输出一个类别"的退化模型。

**答辩风险等级：低。** 评委问"你怎么证明模型不是退化成只会输出一个类别"，现在**可直接用数据反驳**：38 个类全部被预测到、预测分布熵 5.2472/5.2479、早疫病占比 2.6%。

**⚠️ 必须同时向评委如实说明的边界**（否则是另一种"过度声称"风险）：99.47% 是 **同分布（PlantVillage 式实验室摆拍）** 结果；系统对田间实景靠 OOD 拒识兜底，不能把 99.47% 表述为"真实场景准确率"。

### 1.4 赛前最小成本自证方案（建议保留为答辩佐证）

把 `_tmp_model_check.py` 固化成一个正式脚本（如 `scripts/report_model_distribution.py`），输出：**每类准确率表 + 预测类别分布直方图 + 熵**，产物存 `runs/agriguard_v2/`。答辩现场可展示"38×10 抽样逐类正确率 + 预测类别覆盖 38/38"。成本：一次 val 抽样（本机 GPU 约 6 秒/380 张）。

---

## 2. 测试体系完备性审计

### 2.1 现状

- ❌ 无 pytest、无 CI、无覆盖率门禁；全部为**临时脚本**，需人工启动服务后手跑。
- 脚本清单与实测状态（对**当前**代码）：

| 脚本 | 实测结果 | 说明 |
|---|---|---|
| `verify_pipeline.py` | ❌ **4/5** | `ood_rejected` 失败，见 §2.2 |
| `smoke_test.py` | ❌ **崩溃** | `AttributeError: 'list' object has no attribute 'name'`；脚本按旧的"detect 返回 list"写，实际 detect 早已返回 4 元组（9/1 起），从未同步 |
| `verify_mapping.py` | ✅ 通过 | 38 类 0 缺失 0 多余（重构中途一度因 `FALLBACK_MODEL` 改名失败，现已随重构修复） |
| `test_precheck.py` | ✅ 通过 | demo 图 bg_std=32.73 被正确拒；有 `SyntaxWarning: invalid escape sequence '\S'`（docstring 未 raw） |
| `test_gradcam.py` | ✅ 通过 | 生成 `uploads/test_heatmap.jpg` 256×256；但 `generate_cam` 现返回 **tuple**，脚本按"返回 str"打印，输出已失真 |
| `inspect_model.py` | ✅ 通过 | 结构内省正常 |
| `test_llm.py` | ⚠️ 不可用 | 直接 `Path('.env').read_text()`，`.env` 不存在 → 抛异常；且用 `urllib` 直连，与实际 `requests` 路径不一致 |
| `analyze_uploads.py` | ⚠️ 依赖 uploads/ | 直接 `UPLOADS.iterdir()`，**目录被清后必崩** |

### 2.2 回归基线失败详情（真实输出）

```
✅ health
✅ background_rejected
❌ ood_rejected: ok=True, ood_score=0.3025, detections=[蓝莓·健康 0.6903, 大豆·健康 0.3091, 柑橘·黄龙病 0.0003]
✅ normal_recognition
✅ warning_zone
4/5 checks passed   (EXIT=1)
```

原因：`verify_pipeline.py` 的 `make_green_ellipse(1.0)` 期望 ood≈0.242（<0.25 → 拒识），**实际 0.3025** → 落入警告区。同一现象在 HTTP 实测复核（`_tmp_http_check_out.txt` [C]）：`scale=1.0 → ood=0.3025`、`scale=1.4 → ood=0.3036`，**两张合成图现在都是"警告通过"而非"拒识"**。

→ 合成非叶片图不再被拒识；且 `constants.py` 中标定注释仍写"合成椭圆 0.26"，与已部署 v2 权重实测 **0.3025 不符**。这是**回归门禁红灯 + OOD 标定依据与实际不一致**，属正确性/需求未满足。详见 §8 blocking-3。

### 2.3 uploads/ 清理影响面（team-lead 即将执行）

**最高危**：`backend/app/main.py:192` 在 **import 期** `app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)))`，而 `ensure_dirs()` 只在 `@app.on_event("startup")`（import 之后）执行。已**实测复现**（`_qa_uploads_test.txt`）：

```
把 uploads 改名为 _qa_uploads_bak 后：
  python -c "import app.main"
  File ".../backend/app/main.py", line 192, in <module>
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
  RuntimeError: Directory 'D:\shuangti11\ICAN\ican\CNDS\uploads' does not exist
```

> **结论：清理 uploads/ 后再启动服务 → 整个服务起不来（import 阶段即崩）。** 见 §8 blocking-1。修复：在 `mount` 之前调用 `ensure_dirs()`（或该处 `UPLOAD_DIR.mkdir(...)`），或 `StaticFiles(..., check_dir=False)`。

**清 uploads/ 后仍可用的脚本**：`verify_pipeline.py`、`smoke_test.py`（其崩溃与此无关）、`verify_mapping.py`、`test_precheck.py`、`inspect_model.py`、`test_gradcam.py`（`generate_cam` 内部会 `mkdir`）。
**清理后失效**：`analyze_uploads.py`（直接遍历 uploads/）。
**注意**：启动日志显示本次启动 `imaging` 已自动回收 101 个过期文件（保留期 24h）——运行时上传目录本就会自清理，**无需人工删除**；若为磁盘治理，删除后**必须**先修 blocking-1。

### 2.4 关键路径测试缺口（当前仍缺）

| 缺口 | 现状 | 建议 |
|---|---|---|
| 上传体积/类型边界 | ✅ 已补（12MB/后缀白名单/魔数） | 保留 |
| 畸形/超大图片 | ⚠️ 部分 | 加"截断 JPG（有头无尾）"用例 |
| **EXIF 旋转** | ❌ 未处理 | 手机直出竖拍图方向可能错 → precheck/识别受影响；加 `ImageOps.exif_transpose` |
| 并发请求 | ⚠️ 已加 `_model_lock`，但**无并发测试** | 加 5–10 并发 POST，校验响应一致性与无 500 |
| LLM 超时降级 | ⚠️ 代码具备（3.5s/12s），**未真实触发** | mock 一个不响应端点，断言 ≤13s 内回落 `prescription_source="template"` |
| 热力图失败降级 | ✅ 代码具备（返回 `(None, stats)`，主流程置 `heatmap_url=None`） | 加单测：喂损坏图断言 200 且热力图为空 |
| OOD 三区间边界值 | ❌ 无 | 对 0.25/0.32 两侧做边界断言（见 §3） |
| OOD 对"合法拍照但非 38 类"的拒识 | ❌ **已观察到失效**：合成椭圆不拒 | 见 §2.2 |

---

## 3. 验收标准（EARS，可执行）

> 格式：`[Where/While/When/If] <系统> 必须/应该 <行为>`。优先级 P0/P1/P2。

**正常识别流**
- AC-01 [P0] When 用户上传合规纯色背景单叶图，系统**必须**返回 `ok=true`，且 `detections` 长度=3、`detections` 按置信度降序。
- AC-02 [P0] When 识别成功且非 OOD 拒识，系统**必须**返回非空 `heatmap_url` 且该 URL `GET` 返回 `200 image/*`。
- AC-03 [P0] When 识别成功，系统**必须**返回 `prescription`（非空）且 `prescription_source ∈ {"llm","template"}`。
- AC-04 [P1] When 返回成功响应，系统**必须**带 `latency_ms/model_name/model_weight_mb/device`（可观测性）。
- AC-05 [P1] 所有响应**必须**带作品标识 `work`/`signature`，且响应头含 `X-AgriGuard-Signature`。

**形式校验拒绝流**
- AC-06 [P0] If 图中绿色像素占比 < 8% 或缺纯色背景，系统**必须**返回 `ok=false` + 明确 `reason`，且**不得**执行模型推理。
- AC-07 [P0] If 图片真实内容非位图（HTML/文本即便改名 .jpg），系统**必须**拒绝（魔数校验）。
- AC-08 [P0] If 上传体积 > 12MB，系统**必须**拒绝并提示压缩。
- AC-09 [P2] If 图片任一边 < 64px，系统**必须**拒绝。

**OOD 三区间**
- AC-10 [P0] If `ood_score < 0.25`，系统**必须**返回 `ok=false`（拒识），**且仍须**带上 `detections`(top3) 供人工参考。
- AC-11 [P1] If `0.25 ≤ ood_score < 0.32`，系统**必须**返回 `ok=true` 且 `warning` 非空、含"仅供参考"。
- AC-12 [P1] If `ood_score ≥ 0.32`，系统**必须**返回 `ok=true` 且 `warning=null`。
- AC-13 [P1] 系统**必须**在每次响应下发 `ood_reject_threshold`/`ood_warn_threshold` 真值，前端**不得**硬编码。

**LLM 失败降级**
- AC-14 [P0] If 未配置有效 key（缺失/占位符/过短），系统**必须**走模板且 `prescription_source="template"`，**响应时间不应显著增加**。
- AC-15 [P0] If LLM 超时或返回非法 JSON，系统**必须**在 ≤ (连接 3.5s + 读取 12s) 内回落模板，**用户无感**（仍得到完整处方）。
- AC-16 [P1] 系统**必须**如实标注 `prescription_source`，**不得**在模板路径下声称大模型生成。

**热力图失败降级**
- AC-17 [P0] If `generate_cam` 失败返回 `None`，系统**必须**返回 `ok=true`（识别仍有效）、`heatmap_url=null`、`lesion_ratio=null`，前端**不得**崩溃或显示破图。

**（实测对照）** AC-01/02/03/04/05/07/08/09/11/14/16/17 在本次核验中**已通过**；AC-10 **未通过**（合成图 0.3025 落入警告区）；AC-13 后端已下发但**前端仍硬编码**（见 §5.3）。

---

## 4. 数据与证据完整性核验（直通原创性 20 分）

### 4.1 `runs/agriguard_v2/results.csv` 真实性 ✅

| 检查 | 结果 |
|---|---|
| epoch 数 | **30**，序列 1..30 连续无缺 |
| 累计时间 | 单调递增；每 epoch 差 ≈ 80.6–85.7s（第 20 个差 112.6s 属正常抖动） |
| 总时长 | 2490.98s ≈ **41.5 min**，与 `memory/2026-09-15.md` "0.692 小时" 一致 |
| top1 | 0.96592 → 0.99743（单调爬升，尾段平台） |
| top5 | 0.99867 → 0.99992，全程 ≥ top1 |
| val/loss | 0.11564 → 0.00912（整体下降；前 5 均 0.12094 > 后 5 均 0.00923） |
| lr | 前 3 epoch 为 warmup 上升（0.00333→0.00934）后余弦衰减——**非单调属正常**，非篡改特征 |

未发现篡改痕迹；曲线形态与 ultralytics 分类训练一致。

### 4.2 数据集计数 ✅（实测）

| split | 类别数 | 图片数 | 每类 min / max |
|---|---|---|---|
| train | **38** | **48,282** | 800 / 4406 |
| val | **38** | **12,061** | 200 / 1101 |
| 合计 | | **60,343** | |

⚠️ 与文档口径不符：`开发交接文档.md` 写 `train 43,515 / val 10,790`、"54,305 张"；实际 48,282/12,061、60,343。**文档需更正**。
⚠️ 类别严重不平衡：Orange 黄龙病 4406 vs 番茄早疫病等 800（**5.5×**），Tomato YLCV 4286、Soybean 健康 4072。这是 OOD/域泛化风险的现实来源。

### 4.3 权重哈希 ✅

| 文件 | size | sha256(前 16) |
|---|---|---|
| `models/best.pt` | 3,281,538 | `5a076ae67ac8264f` |
| `runs/agriguard_v2/weights/best.pt` | 3,281,538 | `5a076ae67ac8264f` ← **与上完全一致** |
| `runs/agriguard_v2/weights/last.pt` | 3,281,538 | `2dc1fd2aa9232c89`（不同，正常） |
| `models/best_old.pt` | 3,281,915 | `25bb641098d701e3`（旧模型，不同） |
| `models/yolo11n-cls.pt` | 5,790,624 | `c62d41bf96257777` |

→ 生产权重与训练产物 best.pt **同一文件**，证据链成立。

### 4.4 类别映射一致性 ✅

- `_CN_BY_NAME` 38 条 vs `data/plantvillage/train` 38 个目录名：**差集双向为空**（0 缺失 0 多余）。
- `models/best.pt` 内 `names` 38 个与 train 目录名：**完全一致**。
- `verify_mapping.py` 复核：38/38，未映射 []，多余 []。

### 4.5 结论：能否支撑"开发过程可追溯、佐证材料真实有效"的 20 分？

**可作为证据的部分（真实、自洽、可交叉验证）**：
- ✅ 训练产物真实（results.csv 30 epoch 连续、混淆矩阵干净、时间与日志吻合）
- ✅ 数据/权重/映射三者一致（哈希 + 差集机器验证）
- ✅ 4 篇工作日志记录了完整的"问题→机制→方案→验证"闭环（阈值两轮调整 0.40→0.35/0.40→0.25/0.32、热力图 A→C→F 演进），逻辑连贯
- ✅ 重构后代码里已埋**原创指纹**（`ORIGIN_SIGNATURE=HM-AG-2026-0920`，贯穿响应头/响应体/CSS/DOM），对"防抄袭取证"是加分

**仍缺、且会被追问的（建议赛前补齐）**：
1. **训练产物溯源不一致**：`runs/agriguard_v2/args.yaml` 的 `model/data/project/save_dir` 全部指向 `C:\Users\19057\Desktop\hemu-agriguard-master\...`，而 `memory/2026-09-15.md` 声称在 **RTX 4060 / D 盘** 重训。**两者对不上**。评委若核对 `args.yaml`，会问"这模型到底在哪台机器、哪个目录训的？" → 建议：补充一份"环境迁移说明"（C 盘原目录 → D 盘 `D:\CNDS` → 现 `D:\shuangti11\ICAN\ican\CNDS`），或重跑一次短训生成同源 args.yaml，把路径坐实。
2. **文档数据漂移**：交接文档的 train/val 数、`runs/agriguard`(v1) vs 实际 `agriguard_v2`、top1 99.8% vs 99.74% 均需更正为实测值。
3. **无版本控制（无 .git）**：研发过程"可追溯"最硬的证据是提交历史；当前**完全没有**。建议赛前 `git init` 并至少导入当前快照 + 关键节点，形成时间线。
4. **热力图技术表述需校正**：重构后代码自测承认"当前样图着色像素约 **96.6% 来自色温异常通道、仅约 4.0% 来自 Grad-CAM++ 本体**"（`gradcam.py` 内 `gradcam_contrib`/`color_anomaly_contrib`）。对外若仍主宣传"Grad-CAM++ 定位病灶"会与实际输出不符 → 应按"Grad-CAM++ + 色温异常双通道"如实表述。

---

## 5. 演示可靠性风险（巡展 50 分）

### 5.1 冷启动与耗时（**实测**）

| 场景 | 实测 |
|---|---|
| `import app.detector` | 4.03s |
| 进程内首次 `detect()`（含加载 best.pt） | **5.09s** |
| 服务启动预热（重构后 `on_startup` 预加载+一次前向） | **5.84s**（发生在"无人观察"的启动期） |
| POST `/api/v1/predict` 稳态（合规图连打 5 次） | **95 / 95 / 96 / 92 / 97 ms** |
| 首次业务请求（预热后） | 183ms（含首次热力图） |
| 热力图文件 | 20,168 B，`GET` 200 `image/jpeg` |

→ 重构后**首次点击延迟问题已消除**（不再"第一次等 6.7 秒"）。这是一次真实体验提升。

### 5.2 风险清单

| 风险 | 现状 | 演示影响 | 处置 |
|---|---|---|---|
| **清理 uploads/ 后重启 → 服务起不来** | ❌ 已复现 | **致命**：巡展前一夜清理磁盘即全站宕机 | 修 §8 blocking-1 |
| LLM 未配置时 | `llm_enabled=false` → 模板，无网络等待 | 无（但答辩口径需按 §4.5-4 说明） | 若赛前配 key：务必真机连测，断网时最坏 3.5+12s |
| 网络不可控 | 已设 `YOLO_OFFLINE`/`ULTRALYTICS_OFFLINE` | 好 | 保留 |
| 大图耗时 | 已加 `enforce_max_edge(1600)` | 好（原 12MP 慢 ~15×） | 保留 |
| GPU/显存 | 单锁串行，未压测 | 低（单用户演示） | 演示前跑一次 10 并发确认无 500 |
| EXIF 旋转 | 未处理 | 中：手机竖拍图方向错 → 误拒 | 加 `exif_transpose` |
| 并发 | 有 `_model_lock`，无并发测试 | 低 | 补并发用例 |

### 5.3 前后端契约漂移（当前仍存在）

后端已通过 `GET /api/v1/meta` 下发 `ood_reject_threshold=0.25 / ood_warn_threshold=0.32 / supported_crops[...]`，`constants.py` 明令"前端不得硬编码"。但**前端 `app.js` 仍在硬编码**：`app.js:103 " / 拒识阈值 0.25"`、`app.js:146 "…（≥0.32 为正常）"`。这正是文档自己警告的"答辩现场文案与判据对不上的穿帮点"，**需前端消费 `/api/v1/meta` 后方算闭环**。

### 5.4 演示前检查清单（可直接照做）

1. □ 确认 `models/best.pt` 存在且 sha256 以 `5a076ae6` 开头（防误换权重）。
2. □ **先修 uploads 启动 bug**；`run.bat` 启动后看日志出现 `模型预热完成` 与 `模型已加载：best.pt（生产权重）`。
3. □ 离线：`curl /api/v1/meta` → `llm_enabled` 若为 `false`，答辩口径统一说"内置植保知识库模板"，**不要**说"大模型实时生成"。
4. □ 若配了 key：先 `python scripts/test_llm.py` 连通；并**拔网线再打一次** `/predict`，确认 ≤13s 回落且界面正常。
5. □ `GET /health` → `model_ready=true`。
6. □ 用**真实手机照片**（非示例图）走一遍：确认 EXIF 竖拍图不被误拒。
7. □ 无痕窗口打开 `http://127.0.0.1:8000`，走"上传示例图 → 出 top3/热力图/处方"全流程。
8. □ 备好**离线截图/录屏**兜底（网络/GPU 异常时切换）。
9. □ 现场**勿**手动删 uploads/。
10. □ 关闭控制台无关报错（预热的 `_warmup_*.jpg` 已自动清理，确认不残留）。

---

## 6. 回归基线脚本设计（改造前后都能跑）

**目标**：不依赖 uploads/、不依赖网络、不依赖 GPU（可 CUDA 也可 CPU），`pytest` 一键跑。**已按此设计写好并跑通可运行雏形**：`_tmp_regression_baseline.py`（临时脚本，可迁为 `tests/test_baseline.py`）。

> 实测结果：**27/27 ALL PASS**（`_tmp_regression_baseline_out.txt`），证明该基线在当前重构后代码上即可用。
> 关键写法：须用 `with TestClient(app) as c:` 进入上下文以触发 `startup`（否则 `/health` 的 `model_ready` 为 false——属测试写法问题，非产品缺陷）。

层次与断言：

| 层 | 用例 | 依赖 |
|---|---|---|
| 单元 | `imaging.validate_upload`：HTML/文本/超 12MB/合法 PNG/改名 .jpg | 无 |
| 单元 | `precheck.check_leaf_and_background`：合成"白底绿叶"→通过；"灰纹布底"→拒 | cv2 |
| 单元 | `imaging.severity_grade` 边界：None→待评估、0.04→轻、0.05→中、0.19→中、0.20→重 | 无 |
| 单元 | `constants` ↔ `_CN_BY_NAME`：38 条一致；`SUPPORTED_CROP_CN` 14 种 | 无 |
| 单元 | `model_arch.resolve_backbone`：对 best.pt 得 head 有 `.conv/.linear`，target 为 head 前一模块 | torch |
| 单元 | `Prescriber.generate`：无 key → `("template")`；伪造 key 且端点不可达 → 仍 `("template")` 且耗时 < 15s | requests(mock) |
| 契约 | `TestClient(app)`：`/health`、`/api/v1/meta`、`/api/v1/predict` 字段齐备 | httpx（TestClient，**不起服务**） |
| 端到端 | 内存字节 POST `/api/v1/predict`（合成合规图）：`ok=true`、top3、`prescription_source`、`heatmap_url` 可达 | TestClient |
| 降级 | 喂损坏字节 → 200 且 `ok=false`；mock `generate_cam→(None,{})` → `ok=true & heatmap_url=null` | TestClient |

**关键点**：用 FastAPI `TestClient` 而非真起 uvicorn（免端口/免网络）；断言只针对 Spec 定义的值（阈值取自 `constants`，不硬编码），符合"测试不得硬编码实现输出"。

---

## 7. 生产就绪评级（7 维 × 3 档）

| 维度 | 档位 | 依据 |
|---|---|---|
| 测试 + 回归 | **Bronze** | 无 pytest/CI；`verify_pipeline` 4/5、`smoke_test` 崩溃 |
| 契约 | **Silver** | 新增 `/api/v1/meta` 下发真值、响应字段完备、旧路径兼容；但前端仍硬编码阈值 |
| 安全 | **Silver** | 已修存储型 XSS、限体积/类型/魔数、CORS 收敛；仍无鉴权（本机演示可接受） |
| 无障碍 | **Bronze** | 无 a11y 检查证据 |
| 性能 | **Silver** | 稳态 95ms、冷启动移至启动期、大图收敛；无压测 |
| 可观测 | **Silver** | 结构化日志、`latency_ms`、`/health.model_ready` |
| 发布安全 | **Bronze** | 无 .git、requirements 未锁定、**清理 uploads 会致启动失败** |
| **总档（取最低）** | **Bronze** | **未达 Silver，不建议按"商业生产"交付**（赛演可，但须先修 blocking-1） |

---

## 8. 裁决

```
verdict: fail
```

### blocking（仅三类：正确性缺陷 / 需求未满足 / 契约-安全-数据完整性破坏）

1. **[正确性缺陷 · P0]** 删除 `uploads/` 后服务**无法启动**。
   - 证据：`_qa_uploads_test.txt`（改名 uploads 后 `import app.main` → `main.py:192` `RuntimeError: Directory '...uploads' does not exist`）
   - 期望：清理 uploads/ 后重启，服务仍能正常启动（`ensure_dirs()` 前移或在 mount 前建目录 / `check_dir=False`）。
   - 紧迫性：team-lead 已宣布即将清理 uploads/，此缺陷会在下次重启时**直接导致全线不可用**。

2. **[正确性缺陷 · 团队级 P0 规则]** 前端存在 emoji 作 UI 图标。
   - 证据：`_tmp_visual_scan_out.txt`：`frontend/index.html:12  <div class="modal-badge">🌾 禾目 AgriGuard</div>`（U+1F33E）
   - 期望：替换为项目锁定图标库的语义图标（麦穗/叶片 SVG），移除 emoji。
   - 说明：同扫描中另 3 处 `→`（U+2192）位于 Python 注释，非 UI 图标，不算违规。

3. **[正确性缺陷 / 需求未满足]** 回归基线不通过，且 OOD 标定依据与实际不符。
   - 证据：`_qa_verify_pipeline2.txt`（4/5，`ood_rejected` 失败）；`_tmp_http_check_out.txt` [C]（合成椭圆 `scale=1.0→ood=0.3025`、`scale=1.4→ood=0.3036`，均落入警告区而非拒识）；`constants.py` 注释仍写"合成椭圆 0.26"。
   - 期望：非叶片的合成/域外图应 `<0.25` 被拒识（AC-10）；`constants.py` 的标定注释与实测一致；`verify_pipeline.py` 恢复 5/5 或按新模型重标定并同步更新断言与文档。

4. **[正确性缺陷 · 验证资产]** `scripts/smoke_test.py` 直接崩溃，QA 门禁不可用。
   - 证据：`_qa_scripts2.txt`：`smoke_test.py:24 AttributeError: 'list' object has no attribute 'name'`（脚本按 detect 返回 list 写，实际返回 4 元组）。
   - 期望：脚本适配 `(detections, ood, is_ood, is_warning)`，可正常跑通。

### advisory

- **[契约]** 前端 `app.js:103/146` 仍硬编码 `0.25 / 0.32 / 作物清单`，与后端新 SSOT（`/api/v1/meta`）冲突，属答辩穿帮点；建议前端改为读取 `meta`。
- **[证据一致性]** `runs/agriguard_v2/args.yaml` 溯源指向 `C:\Users\19057\Desktop\hemu-agriguard-master`，与 `memory/2026-09-15.md` 的"RTX 4060 / D 盘重训"不一致；建议补环境迁移说明或重跑同源训练。
- **[证据一致性]** 交接文档 train/val 数（43515/10790）、总图数 54305、`runs/agriguard`(v1)、top1 99.8% 均与实测（48282/12061、60343、`agriguard_v2`、99.74%）不符，需更正。
- **[可复现性]** `requirements.txt` 未锁版本、未含 torch/torchvision；`setup.bat` 的 CUDA 版本与实物漂移；建议锁定 `ultralytics==8.4.137`、`torch==2.13.0+cu126`。
- **[版本控制]** 无 `.git`，研发过程"可追溯"缺最硬证据；建议 `git init` + 关键节点提交。
- **[技术表述]** 热力图着色的 ~96.6% 来自色温异常通道、仅 ~4% 来自 Grad-CAM++ 本体，"Grad-CAM++ 定位病灶"表述需校正为双通道。
- **[鲁棒性]** 训练集类别不平衡（5.5×）与田间实景鲁棒性未验证；说明材料中"99.47%"须注明为同分布指标。
- **[测试缺口]** EXIF 旋转、并发、LLM 超时真实触发、OOD 边界值四类用例缺失。

### evidence

- `{artifact: scripts/verify_pipeline.py, line: 81-94, 说明: ood_rejected 用例期望 <0.25，实测 0.3025 → 4/5}`
- `{artifact: .workbuddy/review/_tmp_model_check_out.txt, line: 12-16, 说明: top1=99.47%、38 类全覆盖、熵 5.2472/5.2479、早疫病 2.6%}`
- `{artifact: runs/agriguard_v2/confusion_matrix.png, line: -, 说明: 对角线干净，无整行坍缩}`
- `{artifact: .workbuddy/review/_tmp_fs_audit_out.txt, line: 30-36, 说明: best.pt 与 runs v2 best.pt sha256 一致（5a076ae6…）}`
- `{artifact: .workbuddy/review/_tmp_fs_audit_out.txt, line: 22-25, 说明: train 38/48282、val 38/12061；映射差集双向为空}`
- `{artifact: .workbuddy/review/_tmp_visual_scan_out.txt, line: 10, 说明: index.html:12 emoji 🌾}`
- `{artifact: _qa_uploads_test.txt, line: 36-44, 说明: 删 uploads 后 main.py:192 StaticFiles RuntimeError，服务起不来}`
- `{artifact: .workbuddy/review/_tmp_http_check_out.txt, line: 26-33, 说明: D1–D6 上传校验全部正确拒收（存储型 XSS 已修）}`
- `{artifact: .workbuddy/review/_tmp_http_check_out.txt, line: 12-17 / 43, 说明: 合规图 ok=true、top1 0.9955、src=template、稳态 95ms、热力图可达}`
- `{artifact: _qa_server2.txt, line: 9-13, 说明: 启动预热 5.84s、best.pt 生产权重、target=[9] C2PSA、head=[10] Classify}`
- `{artifact: _qa_scripts2.txt, line: 51-63, 说明: smoke_test.py 崩于 d.name}`
- `{artifact: frontend/app.js, line: 103,146, 说明: 前端硬编码 0.25/0.32，未消费 /api/v1/meta}`
- `{artifact: runs/agriguard_v2/args.yaml, line: 3-4,15-16,116, 说明: 溯源路径 C:\Users\19057\Desktop\hemu-agriguard-master，与日志不符}`

---

## 9. 交付说明 / 临时产物清理

本人**未修改任何项目代码**。仅新增本报告 `CNDS\.workbuddy\review\qa.md`。
为核验而生成的临时脚本（位于 `.workbuddy\review\`，**可删除**）：
`_tmp_fs_audit.py` `_tmp_model_check.py` `_tmp_visual_scan.py` `_tmp_http_check.py` `_tmp_regression_baseline.py` 及对应 `_tmp_*_out.txt` / `_tmp_model_check.json`（其中 `_tmp_regression_baseline.py` 建议**保留并迁为 `tests/test_baseline.py`**）。
项目根下 QA 过程输出（**可删除**）：`_qa_*.txt` `_qa_tmp_diag*.py`、目录 `_qa_pycache\`。
服务状态：本次核验期间启动过 uvicorn（127.0.0.1:8000）用于真实回归，核验结束时已停止（恢复到会话开始前的状态）。
另注：`.venv\Scripts\python.exe` 因 `pyvenv.cfg` 的 home 指向已失效的 `C:\Users\19057\...` 而**不可直接使用**，建议修复 venv 或重建（属环境问题，非项目代码问题）。
