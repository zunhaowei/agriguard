# 前端代码审查报告 · 禾目 AgriGuard

- **审查人**：贾思敏（前端工程师）
- **审查日期**：2026-09-20
- **审查范围**：`CNDS/frontend/`（index.html 2.7KB / styles.css 5.9KB / app.js 6.8KB）+ 与 `CNDS/backend/app/` 的契约一致性
- **审查性质**：**只读审查，未修改任何项目代码**。本报告为改造依据。
- **参照基线**：团队 P0 绝对规则（禁 emoji 功能图标 / 禁硬编码颜色 / 禁 AI 模板味）、iCAN 竞赛约束（原创性 20、巡展现场演示 50、双盲红线）

---

## 0. 事实核验摘要（已实际读码，行号精确）

| 核验项 | 结论 | 证据 |
|--------|------|------|
| emoji 作徽标 | ✅ 确认存在，全仓仅 1 处 | `frontend/index.html:12` |
| 纯文本 `+` 当上传图标 | ✅ 确认 | `frontend/index.html:32` |
| 品牌资源未被引用 | ✅ 确认，`assets/logo_icon.svg`、`assets/logo_full.svg` 全仓无任何引用 | `assets/logo_icon.svg:1`、`assets/logo_full.svg:1` |
| `/static` 挂载范围 | 仅挂载 `frontend/`，**`assets/` 不可达** | `backend/app/config.py:8`、`backend/app/main.py:28` |
| 阈值硬编码 | 前端写死 0.25 / 0.32，后端独立维护同名常量 | `frontend/app.js:103,146` ↔ `backend/app/detector.py:121-122` |
| `createObjectURL` 未 revoke | ✅ 确认，全仓无 `revokeObjectURL` | `frontend/app.js:70` |
| 硬编码颜色 | 前端共 **21 处** 非例外色值 | 见 §B.1 逐行表 |
| 绿色渐变合规 | ✅ `linear-gradient(135deg, var(--green), var(--green-dark))` 为绿色系，**非紫粉**，合规，不报错 | `frontend/styles.css:294` |

---

## A. P0 绝对规则违规（必须修，阻塞项）

### A.1【阻塞 · 需求未满足】emoji 作功能徽标

- **证据**：`frontend/index.html:12` → `<div class="modal-badge">🌾 禾目 AgriGuard</div>`
- **违规条款**：团队 P0-1「UI 代码中不得使用 emoji 表情作为功能图标」。
- **同时浪费既有品牌资产**：`assets/logo_icon.svg`（128×128 图标）+ `assets/logo_full.svg`（460×128 横版，含「禾目 / AgriGuard · 慧眼识农」字样）已存在，却零引用。

**改法（推荐 A-1：拷贝静态资产 + `<img>` 引用，零后端改动、零路径风险）**

1. 将 `assets/logo_icon.svg` 复制一份到 `frontend/logo_icon.svg`（进入 `/static` 挂载范围）。
2. 徽标改为：

```html
<!-- frontend/index.html:12 -->
<div class="modal-badge">
  <img src="/static/logo_icon.svg" alt="" class="badge-logo" width="18" height="18" />
  <span>禾目 AgriGuard</span>
</div>
```

```css
/* frontend/styles.css 追加 */
.badge-logo { display: block; flex: 0 0 auto; }
```

> **为什么不用 inline SVG**：`logo_icon.svg` 内含 `<linearGradient id="top">` 等 `id`。若同页多处 inline，`id` 会重复冲突（渐变互相覆盖）。`<img>` 引用天然隔离 `id` 作用域，且不污染 HTML 体积，是更稳的方案。
> **为什么不改后端加 `/assets` 挂载**：巡展前每减少一处后端改动 = 减少一处零故障风险。拷贝文件是 0 风险。
> **可选 A-2**：若希望未启动后端也能本地预览，可内联，但必须**把两个渐变 `id` 重命名**（如 `agriTop`/`agriBot`）避免冲突。推荐 A-1。

**同步清理死样式**：`.modal-badge` 当前依赖 `gap:8px` 做 emoji 与文字间距（`styles.css:254`），改后仍适用；`font-size:13px` 需保留给文字节点。

---

### A.2【阻塞 · 需求未满足】纯文本 `+` 当上传图标

- **证据**：`frontend/index.html:32` → `<div class="icon">+</div>`，配合 `styles.css:79-84` 的 `font-size:40px`。
- **问题**：文本字形随字体回退变化（`-apple-system`/`PingFang SC`/`Microsoft YaHei` 三端渲染不一致），语义模糊（「+」可读作新增、加号、交叉），不可矢量缩放保证比例。

**改法**：替换为统一描边风格的内联 SVG（与团队图标规范一致：`stroke="currentColor"`、`stroke-width="2"`、`stroke-linecap="round"`、`stroke-linejoin="round"`），取「上传/云箭头」语义：

```html
<!-- frontend/index.html:32 替换 -->
<div class="icon" aria-hidden="true">
  <svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 24 24"
       fill="none" stroke="currentColor" stroke-width="2"
       stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 16V4"/>
    <path d="m7 9 5-5 5 5"/>
    <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>
  </svg>
</div>
```

```css
/* styles.css:79-84 调整 */
.dropzone .icon { color: var(--green); line-height: 1; margin-bottom: 10px; }
.dropzone .icon svg { display: block; margin: 0 auto; }
```

> 该图标为「功能图标」，必须用统一描边 SVG；与 A.1 的品牌 logo（品牌资产，保留原色）职责不同，不混用。
> **规范提示**：`stroke-width="2"` 在 44×44 显示尺寸下视觉偏细，可保留 `viewBox="0 0 24 24"` + `width/height=44`（放大 1.83×），描边等比放大为视觉 ~3.66px，观感协调。若嫌粗，改 `stroke-width="1.75"`。

---

## B. 代码质量与缺陷

### B.1【阻塞 · 需求未满足】硬编码颜色泛滥（P0-3）

P0-3 唯一例外仅 `#fff` / `#000`。逐行证据：

**`frontend/app.js`（9 处）**

| 行号 | 色值 | 语义 | 建议 token |
|------|------|------|-----------|
| 27 | `#2e7d4f` | dragover 边框高亮 | `var(--green)` |
| 31 | `#bfe0cc` | dragleave 边框回落 | `var(--green-border)` |
| 101 | `#64748b` | OOD 分数说明文字 | `var(--muted)` |
| 106 | `#a32d2d` | 拒识标题 | `var(--danger-strong)` |
| 117 | `#f1f5f9` / `#475569` | OOD 参考块 背景/文字 | `var(--surface-ref)` / `var(--ink-soft)` |
| 119 | `#64748b` | 参考块小标题 | `var(--muted)` |
| 131 | `#94a3b8` | 参考块注解 | `var(--muted-soft)` |
| 152 | `#8a6d3b` / `#fff9e6` | 灰区警告 文字/背景 | `var(--warn-fg)` / `var(--warn-bg)` |

**`frontend/styles.css`（12 处，token 定义本身除外）**

| 行号 | 色值 | 语义 | 建议 token |
|------|------|------|-----------|
| 18 | `#f6fbf8` / `#edf5ef` | body 渐变起止 | `var(--bg-top)` / `var(--bg-bottom)` |
| 32 | `#bfe0cc` | `.badge` 边框 | `var(--green-border)` |
| 64 | `rgba(31,94,58,.06)` | 卡片阴影 | `var(--shadow-card)` |
| 68 | `#bfe0cc` | `.dropzone` 虚线 | `var(--green-border)` |
| 87 | `#94a3b8` | `.hint` | `var(--muted-soft)` |
| 102 | `#bfe0cc` | demo 按钮边框 | `var(--green-border)` |
| 108 | `#d8eedf` | demo 按钮 hover | `var(--green-light-hover)` |
| 118 / 141 / 195 | `#f8fafc` | 面板/预览/热力图底 | `var(--surface-soft)` |
| 167 | `#fbfdfc` | `.detection` 行底 | `var(--surface-row)` |
| 219 | `#94a3b8` | footer | `var(--muted-soft)` |
| 228 | `rgba(18,40,30,.45)` | 遮罩层 | `var(--overlay)` |
| 246 | `rgba(15,60,40,.28)` | 弹窗阴影 | `var(--shadow-modal)` |
| 259 | `#bfe0cc` | `.modal-badge` 边框 | `var(--green-border)` |
| 303 | `rgba(31,94,58,.25)` | 主按钮 hover 阴影 | `var(--shadow-btn)` |

**完整 token 方案（在 `styles.css:1-10` 的 `:root` 内补充，保留原有 8 个不动）**

```css
:root{
  /* —— 原有（保留）—— */
  --green:#2e7d4f; --green-dark:#1f5e3a; --green-light:#eaf5ee;
  --ink:#1f2933; --muted:#64748b; --line:#e2e8f0;
  --danger:#c0392b; --card-bg:#ffffff;

  /* —— 新增：绿系扩展（满足 3 档绿阶，替代散落 #bfe0cc/#d8eedf）—— */
  --green-border:#bfe0cc;        /* 浅绿描边：徽标/卡边框/dropzone 虚线 */
  --green-light-hover:#d8eedf;   /* 浅绿交互态：按钮 hover 背景 */

  /* —— 新增：中性面与文字阶（替代 #f8fafc/#fbfdfc/#f1f5f9/#475569/#94a3b8）—— */
  --surface-soft:#f8fafc;        /* 次级面板底 */
  --surface-row:#fbfdfc;         /* 列表行底（极浅绿白） */
  --surface-ref:#f1f5f9;         /* OOD 参考块底 */
  --ink-soft:#475569;            /* 次级正文 */
  --muted-soft:#94a3b8;          /* 提示/脚注文字 */

  /* —— 新增：语义（替代 #a32d2d/#8a6d3b/#fff9e6）—— */
  --danger-strong:#a32d2d;       /* 拒识标题红（比 --danger 更深，用于小字） */
  --warn-fg:#8a6d3b;             /* 灰区警告文字 */
  --warn-bg:#fff9e6;             /* 灰区警告底 */

  /* —— 新增：页面底与遮罩/阴影（替代 5 条 rgba 与渐变 hex）—— */
  --bg-top:#f6fbf8; --bg-bottom:#edf5ef;
  --overlay:rgba(18,40,30,0.45);
  --shadow-card:0 8px 30px rgba(31,94,58,0.06);
  --shadow-modal:0 24px 60px rgba(15,60,40,0.28);
  --shadow-btn:0 8px 20px rgba(31,94,58,0.25);

  /* —— 新增：水印指纹（见 §C，与 token 方案一并落地）—— */
  --agri-signature:"HM-AG-2026-0920";
}
```

**app.js 的 JS 侧改法**：`app.js` 里的 `style.cssText`/`style.color` 应改为**新增语义 class**（CSS 集中管理），不要用 `getComputedStyle` 去读 token（会触发强制重排）。例如：

```css
/* styles.css 新增 */
.ood-ref{ margin:12px 0; padding:10px 12px; background:var(--surface-ref);
          border-radius:8px; font-size:12px; color:var(--ink-soft); }
.ood-ref-title{ margin-bottom:6px; color:var(--muted); font-weight:600; }
.ood-ref-note{ margin-top:6px; color:var(--muted-soft); }
.ood-score{ margin:0 0 12px; font-size:12px; color:var(--muted); }
.warn-box{ margin:0 0 12px; font-size:13px; color:var(--warn-fg);
           background:var(--warn-bg); padding:8px 12px; border-radius:8px; }
.status-error{ color:var(--danger-strong); }
```

```js
// app.js：用 className 取代 style.cssText
ref.className = "ood-ref";
// 标题/注解同理使用 .ood-ref-title / .ood-ref-note
```

> 注意：`--green-border` 等 token 同时被 JS 的 dragover/dragleave 使用，改后应换成 `classList.toggle('is-dragover')` + CSS 规则，彻底消除 JS 里的色值：
> ```css
> .dropzone.is-dragover{ border-color:var(--green); background:var(--green-light); }
> .dropzone{ border-color:var(--green-border); }
> ```

---

### B.2【阻塞 · 契约安全】阈值文案与后端独立维护、必然漂移

- **证据**：前端 `app.js:103` 写死「拒识阈值 0.25」、`app.js:146` 写死「≥0.32 为正常」；后端 `detector.py:121-122` 定义 `ood_reject_threshold=0.25`、`ood_warn_threshold=0.32`。二者**无任何同步机制**。
- **历史证据**（detector.py:120 注释自述）：阈值曾 `0.35/0.40 → 0.25/0.32` 两次调整。**上次调整时前端文案是否同步，无代码保证**——这是典型的静默数据不一致，且直接面向评委展示（`app.js:146` 的阈值会显示在结果区正文字号 12px 的显著位置，一旦漂移，答辩现场「文案说 0.32、后端按 0.32 判、但模型实际按新值」将当场露馅）。

**解耦方案（推荐 T-1：后端在 `PredictResponse` 回传阈值，前端只读响应，零额外请求）**

后端 `backend/app/schemas.py` 的 `PredictResponse` 增加两个字段（默认取 detector 常量）：

```python
class PredictResponse(BaseModel):
    # ... 既有字段 ...
    ood_reject_threshold: Optional[float] = None
    ood_warn_threshold: Optional[float] = None
```

后端 `main.py` 所有 `return PredictResponse(...)`（4 处：`main.py:51,64,88`）补上：

```python
    ood_reject_threshold=detector.ood_reject_threshold,
    ood_warn_threshold=detector.ood_warn_threshold,
```

前端 `app.js` 改为从响应读取（去掉 `app.js:103`、`app.js:146` 的硬编码）：

```js
// 在 render(data) 内
const REJECT = data.ood_reject_threshold ?? 0.25;   // ?? 兜底旧后端
const WARN   = data.ood_warn_threshold   ?? 0.32;
// L103 引用 REJECT，L146 引用 WARN
scoreP.textContent = `分布相似度：${(data.ood_score ?? 0).toFixed(2)}（≥${WARN} 为正常）`;
```

> **T-2（备选，不推荐）**：新增 `GET /config` 返回阈值，前端启动时拉取。缺点：多一次请求、多一个失败点、巡展断网风险。**T-1 优势**：阈值随每次 `/predict` 响应天然同步，无需额外网络往返，旧前端对未知字段自动忽略（向后兼容）。
> **注意 `??` 兼容性**：原生三件套、无构建，`??` 在现代浏览器（含微信内置 X5）、Chrome 均可。若担心极旧内核，用 `(x == null ? d : x)`。

---

### B.3【阻塞 · 正确性缺陷】`createObjectURL` 内存泄漏

- **证据**：`app.js:70` `preview.src = URL.createObjectURL(file);` —— 全仓 grep `revokeObjectURL` **零命中**。
- **后果**：每次上传/换图都新建一个 blob URL，旧 URL 永不释放，其占用的原始图片内存持续累积。评委连续上传演示（换 10+ 张）会累积数十 MB，低配演示机可能触发 GC 抖动甚至卡顿——直接撞上「现场演示零故障」红线。

**修法**：模块级持有当前 URL，赋值新图前 revoke 旧的：

```js
let currentObjectUrl = null;

function setPreview(file) {
  if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl); // 释放上一张
  currentObjectUrl = URL.createObjectURL(file);
  preview.src = currentObjectUrl;
  preview.hidden = false;
}
// handleFile 内 L70-71 替换为：setPreview(file);
// 页面卸载时兜底释放：
window.addEventListener("beforeunload", () => {
  if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
});
```

---

### B.4【阻塞 · 需求未满足 + 正确性】无加载态 / 无请求取消 / 无并发防护

- **证据**：`app.js:77` 仅 `status.textContent = "正在校验图片…"` 一行纯文本；`app.js:81` `fetch('/predict', {method:'POST', body:form})` 无 `AbortController`、无 `disabled` 门禁。`demoBtn` 有 `disabled`（`app.js:45`），但 `dropzone`/`fileInput` **完全无门禁**。
- **后端事实**：`main.py:42-93` 为同步阻塞接口（`async def` 内直接跑 YOLO 推理 + GradCAM + LLM 处方），单次耗时可达秒级。评委不小心连点两次 = 两个并发长请求，浏览器 6 连接池被占，第二次响应顺序错乱可能**覆盖/串写结果区**（`render` 无请求序号校验）。

**修法（加载态 + 并发守卫 + 超时 + 重试）**：

```js
let inflight = null;           // 当前请求的 AbortController
let requestSeq = 0;            // 请求序号，防陈旧响应覆盖

function setLoading(on) {
  dropzone.classList.toggle("is-loading", on);
  fileInput.disabled = on;
  dropzone.setAttribute("aria-busy", on ? "true" : "false");
}

function handleFile(file) {
  if (!file.type.startsWith("image/")) { status.textContent = "请上传图片文件"; return; }

  if (inflight) inflight.abort();              // 取消上一次未完成请求
  inflight = new AbortController();
  const seq = ++requestSeq;

  setPreview(file);                            // 见 B.3
  result.hidden = true;
  detectionsEl.innerHTML = ""; prescriptionEl.innerHTML = "";
  heatmapEl.hidden = true; heatmapImg.src = "";
  status.innerHTML = '<span class="spinner" aria-hidden="true"></span> 正在校验并诊断图片…';
  setLoading(true);

  const timeout = setTimeout(() => inflight && inflight.abort("timeout"), 30000);

  const form = new FormData();
  form.append("file", file);
  fetch("/predict", { method: "POST", body: form, signal: inflight.signal })
    .then((r) => { if (!r.ok) throw new Error("服务返回 " + r.status); return r.json(); })
    .then((data) => { if (seq === requestSeq) render(data); })  // 丢弃陈旧响应
    .catch((err) => {
      if (err.name === "AbortError") {
        if (err.message === "timeout") status.textContent = "诊断超时（>30s），请重试或更换更小的图片";
        return;                                  // 主动取消不报错
      }
      status.innerHTML = '<span class="status-error">诊断失败：' + escapeHtml(err.message) +
        '</span><button type="button" id="retry-btn" class="btn-link">重试</button>';
      document.getElementById("retry-btn").onclick = () => handleFile(file);  // 保留 file 供重试
    })
    .finally(() => { if (seq === requestSeq) { clearTimeout(timeout); setLoading(false); } });
}
```

```css
.spinner{ display:inline-block; width:14px; height:14px; margin-right:6px; vertical-align:-2px;
  border:2px solid var(--green-border); border-top-color:var(--green); border-radius:50%;
  animation:spin .8s linear infinite; }
@keyframes spin{ to{ transform:rotate(360deg); } }
.dropzone.is-loading{ opacity:.6; pointer-events:none; cursor:progress; }
@media (prefers-reduced-motion: reduce){ .spinner{ animation:none; } }
```

> 关键点：①`AbortController` 取消旧请求，杜绝并发串写；②`requestSeq` 序号守卫，即使 abort 未及生效，陈旧响应也进不了 `render`；③30s 超时明确文案；④错误态带「重试」按钮复用原 file；⑤`prefers-reduced-motion` 降级。

---

### B.5【建议 · 正确性/健壮性】`render()` 状态清理不对称 + 数组未防护

- **证据**：
  - `ok===false` 分支（`app.js:92-136`）：清空 `result/heatmap/heatmapImg/prescription/detections`，**但不清理上一次成功结果的 `heatmapEl.hidden` 之外的残留**——实际它清了，OK。
  - 成功分支（`app.js:138-203`）：`app.js:141` 只清 `detectionsEl`，`prescriptionEl.innerHTML=""` 迟至 `app.js:177`。若 `app.js:146-175` 之间抛异常（如 `data.ood_score.toFixed` 遇 `undefined`——`app.js:146` 已用 `|| 0` 兜底，但 `app.js:157` 的 `forEach` 无兜底），则 `prescriptionEl` 保留**上一次的旧处方**，与新的 detections 错配显示。
  - **`app.js:157` `data.detections.forEach(...)` 无 `|| []` 保护**：后端 `schemas.py:29` 默认 `[]`，故当前正常路径不触发；但 OOD 分支 `main.py:73` 显式传 `detections`——**正常分支依赖 schema 默认值，属隐式契约**。任何后端重构（如改为 `Optional[List]` 或前端对接其他后端）即 `TypeError` 崩溃，结果区白屏。
  - `app.js:127` `(d.confidence * 100)` 与 `app.js:164` 同样假设 `confidence` 为 number。

**修法**：①`render` 开头统一重置全部区块（用 `resetResult()` 函数，成功/失败两分支共用）；②所有列表插值加兜底 `const dets = Array.isArray(data.detections) ? data.detections : [];` ③对 `confidence` 做 `Number(d.confidence)||0`。④用 `try/catch` 包裹渲染主体，异常时降级为「结果渲染异常，请重试」而非脏状态。

---

### B.6【建议 · 安全】`innerHTML` 拼串与 XSS 面复核

- **数据源不可信等级**：`detections[].name` 来自模型类别映射（`detector.py:_translate`，相对可信）；但 **`prescription` 五字段（`severity/summary/biological/chemical/tips`）直接来自 LLM 生成的 JSON**（`main.py:80` → `prescriber.generate`），**LLM 输出 = 不可信输入**。同理 `reason`（后端固定文案，可信）、`warning`（后端格式化，可信）。
- **覆盖复核**：逐条核对插值点——
  - `app.js:109` `escapeHtml(data.reason || "请重试")` ✅ 已转义
  - `app.js:124` `escapeHtml(d.name)` ✅
  - `app.js:162` `escapeHtml(d.name)` ✅
  - `app.js:197` `escapeHtml(text)`（处方五字段）✅ 唯一入口
  - **`app.js:153` `warnP.textContent = data.warning`** —— 用 `textContent` 而非 innerHTML ✅ 安全（textContent 天然转义）
  - **`app.js:190` `isDanger = label==="严重程度" && text!=="健康"`** —— `text` 参与逻辑判断但未转义，仅比较，无注入 ✅
- **结论**：**当前所有用户可见插值点要么走 `escapeHtml`，要么走 `textContent`，XSS 面当前闭合**。但存在**架构性风险**：`app.js:105` `status.innerHTML = ... + scoreInfo`、`app.js:132` `ref.innerHTML = html`、`app.js:160/191` `row/block.innerHTML` 均为「字符串拼 HTML」模式，**任何后续改动新增插值点极易漏转义**（现状能救，未来会破）。
- **建议（非阻塞）**：将 `escapeHtml` 保留作为纵深防御，同时**新代码一律用 `textContent` + `createElement` 组装**，逐步淘汰字符串拼 HTML。`app.js:202` 的 `prescriptionEl.innerHTML = '<p class="subtitle">…</p>'`（纯静态文案）无风险，可保留。

---

### B.7【建议 · 无障碍/移动端】逐条改法

| # | 问题 | 证据 | 改法 |
|---|------|------|------|
| 1 | 弹窗无 `role="dialog"`/`aria-modal` | `index.html:11` `<div class="modal">` | 加 `role="dialog" aria-modal="true" aria-labelledby="modal-title"`，标题加 `id="modal-title"` |
| 2 | 无 ESC 关闭 | `app.js:15-21` 仅 click 关闭 | `document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); })` |
| 3 | 无焦点陷阱 | 同上 | 打开时聚焦 `modalClose`（`modalClose.focus()`）；Tab 循环锁在弹窗内；关闭后焦点归还触发元素 |
| 4 | dropzone 键盘不可达 | `index.html:30` `<div id="dropzone">` | 加 `tabindex="0" role="button" aria-label="上传病叶照片"`；`app.js` 加 `keydown` 监听 Enter/Space 触发 `fileInput.click()` |
| 5 | 图片 alt 无意义 | `index.html:45` `alt="预览"` | 改为动态：`alt="待诊断的病叶照片预览"`（或用户文件名）；`index.html:54` 热力图 `alt="Grad-CAM 病灶热力图"` 已较好，可补「，越红表示模型关注度越高」 |
| 6 | 触摸端无拖拽提示 | `index.html:33` 文案仅「点击或拖拽」 | 增加媒体查询/UA 判断，触摸设备显示「轻触选择照片」；拖拽事件在移动端本就不可用 |
| 7 | file input 不可见 | `index.html:31` `hidden` | 保留（由 dropzone 代理），但需确保 dropzone 的 `role="button"` 覆盖可访问性 |

```js
// app.js 追加
function closeModal(){ welcomeModal.classList.add("hidden"); }
modalClose.addEventListener("click", closeModal);
welcomeModal.addEventListener("click", e => { if (e.target === welcomeModal) closeModal(); });
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !welcomeModal.classList.contains("hidden")) closeModal();
});
dropzone.addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});
// 焦点陷阱（简版）
welcomeModal.addEventListener("keydown", e => {
  if (e.key !== "Tab") return;
  const f = welcomeModal.querySelectorAll('button,[href],input,[tabindex]:not([tabindex="-1"])');
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});
```

---

### B.8【建议 · 架构】`app.js` 无模块化

- **证据**：`app.js:1-10` 11 个 `document.getElementById` 直接挂全局（`const` 在顶层脚本 = 全局作用域，进 `window` 的属性命名空间风险）；无 IIFE/模块封装。
- **评估**：**不引入构建的前提下，无需 ES Module**（`<script type="module">` 会引入 `file://` CORS 限制，且后端用 `<script src>` 更稳）。**推荐最小改造**：用 IIFE 包裹，避免污染全局：

```js
(function () {
  "use strict";
  // ... 全部现有代码 ...
})();
```

> 收益：①`const` 不再进全局（避免与未来内联脚本或其他 SDK 撞名）；②`"use strict"` 捕获隐式全局赋值；③零构建、零依赖、零加载顺序变化。**这是低成本高收益的改动，建议区域赛前落地。**

---

## C. 原创水印埋点方案（对应原创性 20 分「可追溯 / 佐证真实有效」）

### C.0 设计原则

1. **多层**：源码注释 / DOM 指纹 / CSS 变量 / 控制台声明 / 隐蔽自证标记 —— 单点易删，多层互为佐证。
2. **克制**：不写满屏版权噪声，每层 1 处、专业可辨识。
3. **双盲合规**：**绝对不含学校名/单位名/指导老师姓名**，仅用团队名「禾目 / AgriGuard」+ 作品标识 + 时间戳 + 指纹。
4. **可维权**：给出「抄袭对照验证法」（见 C.6）。
5. **不动后端、不改接口**，纯前端落地。

**统一签名常量**（贯穿全部层，构成一致性证据链）：

```
作品标识：AGRI-GUARD
版本号  ：v1.0
时间锚点：2026-09-20
指纹命名域：agri-guard
```

---

### C.1 源码注释水印（HTML / CSS / JS 三处，克制）

```html
<!-- frontend/index.html 顶部 <!DOCTYPE html> 之后 -->
<!--
  禾目 AgriGuard · 作物病虫害智能诊断与精准处方系统
  原创作品标识 AGRI-GUARD / v1.0 / 2026-09-20
  本文件前端实现由禾目团队独立设计与编写。任何未署名复用请注明来源。
-->
```

```css
/* frontend/styles.css 顶部 */
/* 禾目 AgriGuard · 视觉系统 agri-guard/v1.0 · 2026-09-20 · 原创设计 */
```

```js
// frontend/app.js 顶部
/**
 * 禾目 AgriGuard 前端交互核心 agri-guard/v1.0
 * 原创作品 · 2026-09-20 · 禾目团队独立实现
 */
```

> 判断标准：**只在文件头各一处**，不做行级刷屏。评委翻源码第一眼即可见，专业不喧宾夺主。

---

### C.2 DOM 指纹（隐蔽但可自证，置于 footer）

在 `index.html:60-62` 的 footer 内加一个**不可见但存在于 DOM** 的节点：

```html
<footer>
  <p>智慧农业 · 减肥减药 · 数字乡村</p>
  <!-- 原创指纹：DOM 结构化签名（视觉不可见，检视器可验证） -->
  <span id="agri-origin-fingerprint"
        data-work="AGRI-GUARD" data-ver="v1.0" data-ts="2026-09-20"
        data-signature="HM-AG-2026-0920"
        aria-hidden="true"
        style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;">
    禾目 AgriGuard 原创作品 · 2026-09-20
  </span>
</footer>
```

> **可验证性**：在浏览器控制台执行 `document.getElementById('agri-origin-fingerprint').dataset.signature` → 返回 `"HM-AG-2026-0920"`。抄袭者若直接复制 HTML，这段会**原样带走**，成为最有力的证据；即便手动删除，C.3/C.4/C.5 仍留存。
> 注：`style` 内联仅做视觉隐藏（无颜色值，不违反 P0-3）；可改为 CSS 类 `.sr-only` 集中管理，更佳。

---

### C.3 CSS 自定义属性指纹（见 §B.1 token 方案已含 `--agri-signature`）

```css
:root{
  /* ... 前述 token ... */
  --agri-signature:"HM-AG-2026-0920";   /* 禾目 AgriGuard 原创标识 */
  --agri-work:"AGRI-GUARD/v1.0";
}
```

> **可验证性**：控制台执行 `getComputedStyle(document.documentElement).getPropertyValue('--agri-signature')` → `"HM-AG-2026-0920"`。
> **隐蔽性**：变量嵌在正常 token 列表里，不被注意；删除它会**连带影响主题系统**（因 JS 可读取该变量做一致性自证，见 C.5），抄袭者往往不敢动。

---

### C.4 控制台输出声明（app.js 末尾，一次性）

```js
// 原创声明（控制台一次性输出，专业克制）
(function agriOriginClaim() {
  const style = "color:#2e7d4f;font-weight:600;";
  console.log("%c禾目 AgriGuard · 作物病虫害智能诊断系统", style);
  console.log("%c原创作品 AGRI-GUARD/v1.0 · 2026-09-20 · 禾目团队独立设计与实现", style);
  console.log("%c署名标识 HM-AG-2026-0920 · 未经许可请勿盗用", "color:#64748b;");
})();
```

> **可验证性**：打开 F12 即见署名，答辩现场可作为「开发过程可追溯」的佐证。
> **双盲合规**：仅团队名 + 作品标识 + 时间戳，无任何学校/单位/人名。

---

### C.5 隐蔽自证标记（运行时一致性校验）

一个**不易被察觉、但可主动触发自证**的机制：控制台输入特定口令，返回完整性证明。

```js
// 隐蔽自证：正常使用完全静默，仅当在控制台输入口令时响应
Object.defineProperty(window, "__agri_guard__", {
  value: Object.freeze({
    work: "AGRI-GUARD",
    ver: "v1.0",
    ts: "2026-09-20",
    signature: "HM-AG-2026-0920",
    verify() {
      const cssSig = getComputedStyle(document.documentElement)
        .getPropertyValue("--agri-signature").replace(/['"]/g, "").trim();
      const domSig = document.getElementById("agri-origin-fingerprint")?.dataset.signature || "";
      const ok = cssSig === this.signature && domSig === this.signature;
      console.log("%c[禾目 AgriGuard] 原创指纹校验：" + (ok ? "完整 ✓" : "已被篡改 ✗"),
                  "color:" + (ok ? "#2e7d4f" : "#a32d2d") + ";font-weight:600;");
      console.log({ cssSignature: cssSig, domSignature: domSig, expected: this.signature });
      return ok;
    }
  }),
  writable: false, configurable: false, enumerable: false   // 不可枚举、不可改，静默存在
});
```

> **隐蔽性**：`enumerable:false` + 双层下划线命名 → 不在 `for...in`、`Object.keys(window)` 中暴露，正常用户与抄袭者都不会注意到。
> **可验证性**：控制台输入 `__agri_guard__.verify()` → 打印「完整 ✓」及三处指纹对照。
> **健壮性**：运行时交叉校验 CSS + DOM 两处签名是否一致 —— **抄袭者若只改了其中一处（如删了 DOM 节点但留了 CSS 变量，或反之），校验即报「已被篡改 ✗」，反而成为更强的侵权证据**。

---

### C.6 维权举证方法（如发现他人盗用）

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 打开疑似抄袭作品，F12 控制台输入 `__agri_guard__` | 若对象存在且 `verify()` 返回「完整 ✓」→ **直接证明其为原样复制**（该符号名几乎不可能撞车） |
| 2 | 输入 `getComputedStyle(document.documentElement).getPropertyValue('--agri-signature')` | 返回 `"HM-AG-2026-0920"` → CSS 层证据 |
| 3 | 查看 `#agri-origin-fingerprint` 节点 `dataset` | `data-work/data-ver/data-ts/data-signature` 四元组完整 → DOM 层证据 |
| 4 | 查看源码头部注释 | 三文件头均含 `AGRI-GUARD/v1.0/2026-09-20` → 源码层证据 |
| 5 | 交叉验证 | **五层中任一层存活 + 时间戳早于对方 Git 提交/发布记录 = 形成完整证据链** |

**证据链强度**：单一水印可被辩称「巧合」；**五层（源码注释 + DOM + CSS 变量 + 控制台 + 运行时自证）同时命中且时间戳一致，构成「同一作者、同一时间锚点」的强证明**。时间锚点 `2026-09-20` 与项目提交历史（`.workbuddy/memory/`）可交叉印证，满足原创性 20 分「佐证材料真实有效」。

**落地成本**：约 40 行代码，零依赖、零外部请求、零性能开销（自证对象懒加载，仅控制台触发时才计算）。

---

## D. 国奖级演示增强建议（巡展「现场演示效果 50 分」，只提 2 项）

> 筛选标准：提升现场观感/说服力 + 实现简单 + 风险低 + 区域赛前可完成。

### D.1【高 ROI】结果区展示推理耗时 + 模型信息（体现「轻量」）

- **做法**：后端 `/predict` 已在同步流程中，只需在 `main.py` 用 `time.perf_counter()` 包裹推理段，`PredictResponse` 增加 `latency_ms: Optional[float]`、`model_name: Optional[str]`（取自 `MODEL_PATH.name` 或 `best.pt`）；前端在 `detectionsEl` 顶部（`app.js:147` 附近）显示「YOLO11 · 本地推理 312ms · 无需联网」。
- **说服力**：直接回应「轻量、可落地、田间可用」——评委最关心的实用性 25 分。展示「本地推理毫秒级」比空谈架构有力得多。
- **工作量**：后端 ~8 行，前端 ~10 行。**半天内完成。**
- **风险**：低。仅新增可选字段，旧前端忽略即兼容。
- **降级方案**：若后端时间紧，前端可先用 `performance.now()` 包 `fetch` 测端到端耗时（含网络），标注「端到端」。但**推荐后端计时**更准确（纯推理，不受网络抖动影响，演示更稳）。

### D.2【高 ROI】热力图与原图的滑动对比（体现「可解释」）

- **做法**：结果区已有 `#preview`（原图）与 `#heatmap-img`（Grad-CAM）。新增一个「对比」视图：两张图叠放，用 CSS `clip-path: inset(0 X% 0 0)` 做**拖动分割线**（`input[type=range]` 或指针拖动），滑动即可看到「原图 ↔ 病灶热力图」的渐变揭示。
- **说服力**：把「可解释 AI / Grad-CAM」从静态图变成**可交互演示**，答辩时手动滑动分割线，视觉冲击强，是巡展「演示效果」的加分动作，也呼应原创性（体现设计巧思）。
- **工作量**：纯前端 ~60 行（HTML 容器 + CSS + 一个 range 事件监听）。**1 天内完成。**
- **风险**：中低。①需两图尺寸对齐（`preview` 与 `heatmap-img` 均 `object-fit:contain`，需统一容器宽高比）；②移动端触摸拖动需用 pointer 事件。
- **降级方案**：若时间不足，退化为**并排双图 + 「显示/隐藏热力图」toggle 按钮**（~15 行），仍比现状「单图叠列」有交互感；再降级则保留现状，仅补 `alt` 文案。

> **明确否掉**：「历史记录本地留存」——需设计存储结构、清理策略、隐私提示，且演示时若 localStorage 有脏数据反而尴尬，ROI 低于上述两项，本轮不做。

---

## E. 交付前检查（本轮审查结论）

- [x] 已实际读码（index.html / app.js / styles.css / schemas.py / main.py / detector.py / config.py / 两个 logo svg），文件:行号均经核对。
- [x] emoji 扫描：全仓仅 `index.html:12` 一处（正则 `[\x{1F300}-\x{1F9FF}...]`）。
- [x] 紫粉渐变核查：`styles.css:294` 为绿色系渐变，**合规，不报错**。
- [x] 未修改任何项目代码（仅新增本报告）。
- [x] 水印方案双盲合规：全篇无学校名/单位名/指导老师姓名。

---

## F. 结构化裁决

```
verdict: fail

blocking:
  - {违反项: "P0-1 禁止 emoji 作功能图标（需求未满足）", 证据: "frontend/index.html:12 → <div class=\"modal-badge\">🌾 禾目 AgriGuard</div>；同时 assets/logo_icon.svg、assets/logo_full.svg 全仓零引用", 期望: "移除 emoji，改用品牌 SVG：将 logo_icon.svg 复制进 frontend/ 并以 <img src=\"/static/logo_icon.svg\"> 引用（assets/ 不在 /static 挂载范围，config.py:8 已确认）"}
  - {违反项: "P0-1 功能图标须为统一描边矢量（需求未满足）", 证据: "frontend/index.html:32 → <div class=\"icon\">+</div> 用纯文本加号作图标的；styles.css:79-84 以 font-size:40px 放大", 期望: "替换为上传/云箭头语义的内联 SVG，stroke=currentColor/stroke-width=2/round 描边风格"}
  - {违反项: "P0-3 禁止硬编码颜色（需求未满足）", 证据: "frontend/app.js:27,31,101,106,117,119,131,152 共 9 处；frontend/styles.css:18,32,64,68,87,102,108,118,141,167,195,219,228,246,259,303 共 12+ 处非 #fff/#000 色值", 期望: "全部收敛至 :root 语义 token（方案见 §B.1），JS 侧改用语义 class 替代 style.cssText"}
  - {违反项: "契约安全/数据完整性：阈值前后端独立维护、无同步机制（契约安全）", 证据: "frontend/app.js:103 写死「拒识阈值 0.25」、app.js:146 写死「≥0.32 为正常」 ↔ backend/app/detector.py:121-122 ood_reject_threshold=0.25 / ood_warn_threshold=0.32 独立定义；detector.py:120 注释自述阈值曾 0.35/0.40→0.25/0.32 两次变更", 期望: "PredictResponse 增加 ood_reject_threshold/ood_warn_threshold 字段由后端回传，前端从响应读取并兜底，消除双份真源"}
  - {违反项: "正确性缺陷：createObjectURL 内存泄漏", 证据: "frontend/app.js:70 preview.src = URL.createObjectURL(file)，全仓无 revokeObjectURL", 期望: "持有 currentObjectUrl 引用，赋值新图前 revokeObjectURL 旧值，beforeunload 兜底释放"}
  - {违反项: "需求未满足+正确性：无加载态/无并发守卫/无超时（撞「现场演示零故障」红线）", 证据: "frontend/app.js:77 仅一行纯文本状态；app.js:81 fetch 无 AbortController、无请求序号；dropzone/fileInput 无 disabled 门禁（仅 demo-btn app.js:45 有）；backend/app/main.py:42-93 为秒级同步阻塞接口", 期望: "引入 AbortController + 请求序号守卫 + spinner 加载态 + 30s 超时文案 + 错误重试按钮 + disabled 门禁（方案见 §B.4）"}

advisory:
  - {建议项: "render() 两分支状态清理不对称、detections 未做 || [] 防护、confidence 未做类型兜底", 理由: "app.js:157 forEach 无兜底（现依赖 schemas.py:29 默认 []），app.js:177 迟清 prescriptionEl，中途抛异常会残留旧处方与新 detections 错配；统一 resetResult() + Array.isArray 兜底 + try/catch 降级"}
  - {建议项: "innerHTML 字符串拼 HTML 模式为未来 XSS 隐患", 理由: "当前所有插值点（app.js:109,124,162,197 走 escapeHtml；app.js:153 走 textContent）XSS 面已闭合，但 app.js:105/132/160/191 的拼串模式在后续改动中极易漏转义；建议新代码一律 createElement+textContent"}
  - {建议项: "无障碍与移动端缺陷 7 项", 理由: "弹窗缺 role=dialog/aria-modal、无 ESC/焦点陷阱；dropzone 无 tabindex/role=button/键盘触发；preview alt=「预览」无意义；触摸端无拖拽提示；改法见 §B.7"}
  - {建议项: "app.js 无模块封装，顶层 const 进全局", 理由: "不引入构建前提下，用 IIFE + 'use strict' 包裹即可消除全局污染、捕获隐式全局赋值，零风险低成本，见 §B.8"}
  - {建议项: "D.1 结果区展示推理耗时与模型信息", 理由: "强化「轻量本地推理」说服力（实用性 25 分），后端约 8 行、前端约 10 行，半天完成，风险低"}
  - {建议项: "D.2 热力图与原图滑动对比", 理由: "将 Grad-CAM 从静态图变为可交互演示，契合巡展「演示效果 50 分」，纯前端约 60 行，1 天完成，需处理两图尺寸对齐"}

evidence:
  - {artifact_ref: "frontend/index.html", line: 12, 说明: "emoji 🌾 作徽标，唯一 emoji 命中点"}
  - {artifact_ref: "frontend/index.html", line: 32, 说明: "纯文本 + 作上传图标"}
  - {artifact_ref: "frontend/app.js", line: 70, 说明: "createObjectURL 未配套 revokeObjectURL"}
  - {artifact_ref: "frontend/app.js", line: 77, 说明: "加载态仅纯文本，无 spinner/禁用"}
  - {artifact_ref: "frontend/app.js", line: 81, 说明: "fetch 无 AbortController/信号"}
  - {artifact_ref: "frontend/app.js", line: 103, 说明: "硬编码「拒识阈值 0.25」"}
  - {artifact_ref: "frontend/app.js", line: 146, 说明: "硬编码「≥0.32 为正常」"}
  - {artifact_ref: "frontend/app.js", line: 157, 说明: "detections.forEach 无 || [] 防护"}
  - {artifact_ref: "frontend/styles.css", line: 294, 说明: "绿色系渐变，合规（非紫粉），确认不报错"}
  - {artifact_ref: "backend/app/detector.py", line: 121, 说明: "ood_reject_threshold=0.25，前端硬编码同值的另一份真源"}
  - {artifact_ref: "backend/app/detector.py", line: 122, 说明: "ood_warn_threshold=0.32，前端硬编码同值的另一份真源"}
  - {artifact_ref: "backend/app/config.py", line: 8, 说明: "FRONTEND_DIR=BASE_DIR/frontend，assets/ 不在挂载范围"}
  - {artifact_ref: "backend/app/main.py", line: 28, 说明: "/static 仅挂载 frontend/"}
  - {artifact_ref: "assets/logo_icon.svg", line: 1, 说明: "既有品牌图标资源，全仓零引用，应复用"}
  - {artifact_ref: "assets/logo_full.svg", line: 21, 说明: "含「禾目 / AgriGuard · 慧眼识农」横版品牌资源，零引用"}
```

---

**审查完毕。** 所有 `文件:行号` 均经实际读码核对。本报告为唯一交付物，未改动任何项目源码。
