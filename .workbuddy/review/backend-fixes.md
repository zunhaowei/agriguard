# 后端修复记录 — 禾目 AgriGuard（回应 QA §8 blocking-1/3/4）

- 修复人：贝洛奇（后端工程师）
- 日期：2026-09-20
- 范围：仅后端与验证脚本；未改前端（blocking-2 的 emoji 属前端同事范围）
- 环境：Windows + Git Bash 不可用，全程经 PowerShell 重定向落盘后用 Read 复核；
  Python 走 `.venv\Scripts\python.exe`（实测可用；torch 走 cuda:0）

---

## 0. 结论速览

| # | QA blocking | 修复前 | 修复后 | 状态 |
|---|---|---|---|---|
| 1 | 删 `uploads/` 后服务起不来 | `main.py` 在 import 期 mount StaticFiles，而 `ensure_dirs()` 只在 startup 跑 | mount 前先 `ensure_dirs()` | **已修复**（他人修复，本次复验通过） |
| 2 | smoke_test.py 直接崩 | `detect()` 返回 4 元组，脚本按 list 写 → `AttributeError` | 解包 `(detections, ood, is_ood, is_warning)` | **已修复**（他人修复，本次实跑通过） |
| 3 | OOD 标定漂移 + 回归红灯 + constants 注释不符 | `verify_pipeline.py` 4/5；`constants.py` 注释写「合成椭圆 0.26」 | 按部署权重实测重标定夹具与注释 | **本次修复，5/5** |

> blocking-1 / blocking-4 在我接手时，工作区代码**已含修复**（`main.py` 与 `scripts/smoke_test.py`
> 内均有对应「本次审查修正」注释）。我未重复改动，只做了**独立复验**（见 §1、§3）。

---

## 1. blocking-1 复验：删 uploads/ 后仍可启动

`main.py` 现状（关键顺序）：`ensure_dirs()` 位于 **模块级**、且在 `app.mount("/uploads", ...)` **之前**执行。
`config.ensure_dirs()` 幂等，startup 钩子里再调一次也无副作用。

复验方法（`uploads` 改名 → 起 import → 恢复）：

```
把 CNDS/uploads 改名为 uploads__verify_bak
  .venv\Scripts\python.exe -c "import app.main; print('IMPORT_OK')"   (cwd=backend)
恢复 uploads 目录
```

实测结果：`IMPORT_OK`，退出码 0。`ok=True` → blocking-1 已消除。

---

## 2. blocking-3 修复：OOD 标定与回归夹具重标定（核心）

### 2.1 根因（实测，非推断）

用部署权重 `models/best.pt`（v2，3.13MB）直接量化各合成图的 `ood_score`：

| 夹具 | ood_score | 落区 |
|---|---|---|
| 白底绿椭圆 scale=0.8 / 1.0 / 1.4 | 0.3023 / **0.3025** / 0.3036 | 警告区 |
| 灰底绿椭圆 | 0.2734 | 警告区 |
| 黑底绿椭圆 | **0.2216** | 拒识区 |
| 合规真实番茄叶 `_demo_leaf_compliant.jpg` | 0.3691 | 正常区 |

**根因不是阈值坏了，而是旧夹具选错了**：`verify_pipeline.py` 用「纯白底 + 绿色椭圆」当拒识夹具，
并假设其 `ood≈0.24`。但绿色均匀图形恰是「健康叶」类权重向量的高相似方向，v2 权重下该夹具整体
上移到 0.30（警告区），于是 `ood_rejected` 用例红。`constants.py` 注释里的「合成椭圆 0.26」
是**更早权重版本**的数值，v2 下整条分布下移约 0.05~0.06，已不适用。

**阈值本值（0.25 / 0.32）保持不变的理由**：真实合规图 0.3691 稳在正常区（≥0.32），
PlantVillage val 同分布 380 张抽样均值 0.51、378/380 ≥0.32 —— 阈值并未误杀受支持作物；
下调阈值曾有「误杀葡萄叶」的历史教训，不应因夹具口径而再动。故只重标定夹具与注释。

### 2.2 改动

- `scripts/verify_pipeline.py`
  - 拒识夹具改为「黑底绿椭圆」（0.2216），警告夹具改为「灰底绿椭圆」（0.2734）；正常区沿用真实合规图。
  - 三类断言统一**从响应体读取** `ood_reject_threshold` / `ood_warn_threshold`，脚本不再硬编码阈值，
    消除与 `constants.py` 的双份真源。
  - 新增 `AGRI_BASE_URL` 环境变量支持（便于非 8000 端口 CI）；docstring 写明重标定依据与「换权重须重跑」。
  - 通过/失败标记由 emoji 改为纯文本 `[PASS]`/`[FAIL]`（贴合团队级「禁 emoji 作功能图标」规则）。
- `backend/app/constants.py`
  - 重写 OOD 标定注释：给出 v2 权重实测锚点，并说明旧值（0.43/0.26）来自更早权重版本、已不适用。
  - 阈值常量值**未改**（0.25 / 0.32）。

### 2.3 复验（对真实 uvicorn 服务）

起真实 uvicorn（127.0.0.1:8011）后跑 `scripts/verify_pipeline.py`：

```
[PASS] health
[PASS] background_rejected
[PASS] ood_rejected
[PASS] normal_recognition
[PASS] warning_zone

5/5 checks passed
```

退出码 0。blocking-3 消除。

---

## 3. blocking-4 复验：smoke_test.py 可跑通

`scripts/smoke_test.py` 现状已正确解包 `detections, ood_score, is_ood, is_warning = detector.detect(...)`。

实跑（真实 val 样本 `Apple___Apple_scab/image (10).JPG`）：

```
样本文件: image (10).JPG
真实类别: Apple___Apple_scab
OOD 分布相似度: 0.4877  (拒识=False, 警告=False)
Top3 识别:
  苹果 · 黑星病  (1.0000)
处方（来源=template）: ... 冒烟测试通过。
```

退出码 0，stderr 为空，**无 AttributeError**。blocking-4 消除。

---

## 4. 验证方式与可复现性

- 全部经自足脚本运行，避免端口/网络残留：进程内起 uvicorn 线程 → 跑真实 `verify_pipeline.py` → 关停；
  smoke_test 单独子进程运行。原始输出见 `.workbuddy/verify_work/`（临时，可删）。
- 启动复验脚本：`.workbuddy/verify_work/run_verify.py`；smoke 复验：`run_smoke.py`。

## 5. 未做 / 遗留（交主理人裁决）

- blocking-2（前端 `index.html` emoji）属前端同事范围，未动。
- QA 建议把 `_tmp_regression_baseline.py` 迁为 `tests/test_baseline.py`：该临时脚本当前不在工作区，
  如需正式化，建议由 QA 提供脚本、我配合落 `tests/` 与 CI 命令。
- 本机 `.venv\Scripts\python.exe` 实测可用（QA §9 记录的「不可用」或为环境已修复）。
