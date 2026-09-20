# 禾目 AgriGuard — UI/UX 诊断与国奖级视觉改造方案

> 作者：颜好看（UI/UX 设计师）
> 日期：2026-09-20 ｜ 赛事：iCAN 创新创业大赛 · 创新赛道 · 目标国家级一等奖
> 对象：**存量作品改造**，非从零设计。所有结论已基于实际读取源码与品牌资产得出。
> 约束：前端为原生 HTML/CSS/JS（无构建、无框架、无 npm）。本方案全部为「可直接复制进现有文件」的形态。

---

## 0. 判读依据（已实际读取的文件）

| 文件 | 行数 | 关键发现 |
|---|---|---|
| `frontend/index.html` | 66 | 单页结构；`modal-overlay` 欢迎弹窗为阻塞式；`modal-badge` 内含 emoji 字符 `U+1F33E`（稻穗，第 12 行）；dropzone 用文本 `+`（第 32 行）；结果区 `#result` 默认 `hidden` |
| `frontend/styles.css` | 316 | `:root` 仅 8 个变量；**至少 14 处硬编码色值**；卡片 `1px border + 0 8px 30px` 构成「幽灵卡片」；全站无 `:focus-visible`、无 `prefers-reduced-motion` |
| `frontend/app.js` | 210 | **内联 style 硬编码色值 12 处**（`#64748b`/`#a32d2d`/`#f1f5f9`/`#475569`/`#8a6d3b`/`#fff9e6` 等）；`分布相似度 ≥0.32 为正常` 直接暴露给农户（第 146 行）；OOD 拒识分支仅有灰底文字块，无视觉层级 |
| `assets/logo_icon.svg` | 19 | **品牌真实色系 = 叶绿 `#22C55E → #15803D` + 青色虹膜 `#06B6D4 / #0E7490`**。青色是品牌资产里存在、但 UI 完全未使用的第二主色 |
| `assets/logo_full.svg` | 23 | 横版：`禾目`（`#166534`）+ `AgriGuard · 慧眼识农`（`#0E7490`，字距 1） |
| `assets/logo_heyhe.jpg` | 图 | 彩色效果图：一枚「叶脉构成的眼睛」，虹膜为青色同心圆 —— 与「慧眼识农」语义闭环 |

**核心判断一句话**：这个作品的差异化护城河是 **「看得见病灶」（热力图可解释性）+ 「不需要先选作物」（自动识别种类）**，竞品「智驭未来队」两点都缺。当前 UI 却把这两个卖点埋在结果区最底部和一句 12px 灰字里。**设计改造的第一原则：把差异化卖点提到评委视野的第一屏、第一眼。**

---

## A. 设计诊断

### A0. 品牌资产诊断（先说最容易被忽略的）

`logo_icon.svg` / `logo_full.svg` / `logo_heyhe.jpg` 三份资产**在页面里一次都没出现**（`index.html` 无 `<img>` 引用任何 logo）。这是本次改造性价比最高的一处：

1. **品牌色系未被激活**：现在 UI 是「一锅绿」，而品牌实际是 **绿（叶）+ 青（眼）** 双色。青色 `#0E7490` 恰好可以承担「AI 识别 / 技术」这一语义维度，与竞品的「纯绿农业风」和「后台蓝」都拉开距离。
2. **语义资产未被利用**：logo 是「叶脉中的眼睛」，直接对应「慧眼识农」与本产品的「看懂病灶」。Hero 区用 logo 替代纯文字标题，可以**零成本获得「这是一个有品牌的作品」的第一印象**（评委对「有品牌意识」的加分是实打实的）。
3. **favicon 缺失**：`<head>` 无 `link rel="icon"`，浏览器标签页显示默认空白图标。演示投屏时标签页可见，属于免费失分项。

---

### A1. 逐区块问题清单

分级口径：**P0** = 直接影响评委观感/演示成功率/合规；**P1** = 影响信息传达效率；**P2** = 工艺细节。

---

#### A1-1 欢迎弹窗（`modal-overlay` / `modal`）

| 级别 | 问题 | 当前观感 | 期望观感 |
|---|---|---|---|
| **P0** | **阻塞式弹窗卡在演示路径第 0 步**。评委看演示时，第一动作是「点开始使用」，多一次点击、多 5 秒阅读、还遮住了首屏 | 「打开先被拦一下，读完两段话才能动手」 | 「打开即见产品本体，拍摄规范以**常驻卡片**形式贴在输入端，永远看得到」 |
| **P0** | emoji 字符 `U+1F33E`（稻穗）出现在 `modal-badge`（`index.html:12`）作为品牌标记 | 电商贺卡感，与「专业农业仪器」气质相反 | 用 `logo_icon.svg` 内联 20px，或图标库 `sprout` 语义图标 |
| **P1** | 正文三段共 ~110 字，`line-height:1.85` 居中弹窗内左对齐，扫读效率低 | 「一段说明书」 | 拆成 3 条 4 字短句 + 图标：`单片叶片` / `纯色背景` / `正上方拍摄` |
| **P1** | 弹窗关闭即信息消失，用户拍摄时反而看不到规范 | 「看的时候不用，用的时候看不到」 | 规范沉淀到上传卡片常驻 |
| **P2** | `border-radius:20px` 超出手册「卡片圆角上限 16px」 | 略「糖果感」 | 统一 `--radius-lg:16px` |
| **P2** | `modal-btn` 绿色渐变 `#2e7d4f→#1f5e3a`（合规，非紫粉）但产品型界面建议纯色 | 尚可，但偏「营销页」 | 纯色 `--accent` + hover 变深，更克制 |

**结论：欢迎弹窗不应在演示路径中存在。** 但它的内容（拍摄规范）有价值 —— **内容保留、载体改变**：改为「拍摄规范卡」内联进上传区，弹窗降级为可选帮助（`?` 按钮触发，默认不弹）。

---

#### A1-2 Hero 区

| 级别 | 问题 | 当前观感 | 期望观感 |
|---|---|---|---|
| **P0** | `AI 辅助制作` 徽标（12px 胶囊）**占据 Hero 第一视觉落点**，且用 `display:inline-block` 居中，位于 H1 正上方 | 「第一眼看到的是免责声明，不是产品」 | 合规标注**保留但降权**：移到页面顶部条**右对齐**小胶囊（与左对齐品牌并列），并在页脚再出现一次。合规、得体、不抢戏 |
| **P1** | Hero 是「居中标题 + 副标题」的通用型，无品牌资产、无产品证据 | 「任何一个 AI 生成的落地页都长这样」 | 左文右标：左侧「禾目 AgriGuard + 一句人话」，右侧 `logo_icon.svg` 96px。**非对称**，且一眼看到品牌 |
| **P1** | 副标题「拍一张病叶照片，秒出诊断与防治处方」——「秒出」不可验证，属空洞修饰 | 尚可但「秒出」偏夸 | 改为可验证的具体动作：「拍一张病叶照片，自动识别作物与病害，给出防治处方」 |
| **P2** | `h1` 内 `span` 用 `font-weight:300`（第三档字重，违反「仅 400/500」规范） | 字重层级混乱 | 统一 400/500，用**字号差**建立层级 |
| **P2** | `letter-spacing:1px` 加在 34px 中文标题上，中文应负字距 | 略松散 | `-0.02em` |

---

#### A1-3 上传卡片 / 空状态

| 级别 | 问题 | 当前观感 | 期望观感 |
|---|---|---|---|
| **P0** | 空状态只有一个文本 `+`（`font-size:40px`），无图标、无示例、无「拍成这样」的参照 | 「一个加号，我不知道该传什么、拍成什么样」 | 图标库 `upload-cloud` 40px + 一行主文案 + **一张正确的示例缩略图**（直接复用 `_demo_leaf_compliant.jpg`） |
| **P0** | 示例图入口 `demo-bar` 按钮视觉权重过低（`--green-light` 底色 + 13px 字号，高约 30px），而它是**演示时最高频的按钮** | 「这么重要的按钮藏在灰字后面」 | 提升为次级主按钮（描边 + `--accent` 文字 + 44px 高），或与 dropzone 并列的双入口 |
| **P1** | 两行 `hint` 各 `font-size:12px` + `color:#94a3b8`（对比度约 2.6:1，**不达 4.5:1**） | 灰得看不清，等于没写 | 提升到 `--muted` `#64748B`（4.76:1）、13px，并用图标分隔三要点 |
| **P1** | `current可识别作物` 折叠在最后，「不需要先选作物」是核心卖点却被折叠 | 卖点被藏起来 | 折叠保留（避免噪音），但摘要文案改为价值断言：「**不用先判断是什么作物 —— 14 种作物自动识别**（点击查看）」 |
| **P2** | 拖拽态在 `app.js` 里用 `style.borderColor = "#2e7d4f"` 硬编码，且 `dragleave` 后无法恢复原态 | 拖拽反馈不一致 | 改用 class 切换 + token 变量 |
| **P2** | `dropzone` 无 `:focus-visible`，键盘用户无法感知焦点 | 键盘不可用 | 加焦点环 |

---

#### A1-4 结果区信息层级（**本次改造最关键的一节**）

当前顺序：`分布相似度小字` → `警告条` → `Top3 置信度列表` → `热力图` → `处方五区块`。

**问题：这个顺序是「按模型内部流程排的」，不是「按评委认知顺序排的」。**

| 级别 | 问题 | 当前观感 | 期望观感 |
|---|---|---|---|
| **P0** | **最该先看到的「结论」缺席**。现在第一行是 `分布相似度：0.43（≥0.32 为正常）` —— 评委第一眼看到的是一个没人看得懂的技术参数 | 「这页在跟我讲它内部怎么算的」 | 第一眼是**病名 + 可信度 + 严重程度**（病历卡），一句话看懂 |
| **P0** | **差异化卖点（热力图）排在 Top3 列表之后**，需要滚动才看到 | 「最有说服力的证据被埋了」 | 结论卡之后**紧接**热力图，形成「说是这个病 → 你看我真看到了病灶」的强证明链 |
| **P0** | `分布相似度 ≥0.32 为正常` 直接暴露给农户，与「面向小农户」定位冲突 | 「农户看不懂，评委会觉得产品定位不清」 | **双层表达**：面向农户给「可信度 高/中/低」胶囊；技术原值收进「技术详情 ▸」折叠，评委想看有、农户不被打扰 |
| **P1** | Top3 全量展示，但 rank 2/3 对「怎么办」没有指导价值，反而稀释第一个答案 | 「三个答案并列，到底哪个？」 | 结论卡放第一名；「其他可能（2）▸」折叠 |
| **P1** | `严重程度` 混在处方五区块的第一块，与「诊断概述」并列，权重被浪费 | 「严重程度」被当成一小段文字 | 严重程度**上提到结论卡**，做成色标（健康/轻/中/重） |
| **P1** | 处方五区块（严重程度/诊断概述/生物防治/化学用药/日常管理）**平铺等权**，农户真正要执行的「怎么办」不突出 | 「五段一样重，不知从哪看起」 | 三段式：`生物防治` + `化学用药` + `日常管理` 为执行区（带图标），`诊断概述` 上并到结论卡 |
| **P2** | `detections` 与 `prescription` 之间用 `border-top` 分隔，`heatmap` 也用 `border-top`，**同类分隔符表达不同层级** | 层级模糊 | 分区标题 + 卡中卡（sunk surface），间距建立分组 |
| **P2** | 置信度用 `font-family:monospace` 但无 `tabular-nums` 视觉一致性弱 | 尚可 | 数字统一 `font-feature-settings:"tnum"` |

---

#### A1-5 热力图

| 级别 | 问题 | 当前观感 | 期望观感 |
|---|---|---|---|
| **P0** | **无图例、无解释**。JET 彩虹色带（蓝→绿→黄→红）对红绿色盲不友好，且农业用户不天然理解「红=病灶重」 | 「一堆彩色，不知道红是好是坏」 | 图例条 `关注度：低 ▁▂▃▅▆▇ 高` + 一行说明「颜色越暖，表示模型越关注的病斑区域」 |
| **P1** | `label` 仅二字「病灶定位」，不解释这是什么技术 | 「不知道这是 AI 猜的框还是真定位」 | 「模型注意力可视化（Grad-CAM）」+ 「这是什么？▸」折叠解释 |
| **P1** | 后端色带本身不可控（前端只能加图例）。若后端可改，建议换 `viridis`/`inferno` 或「青→琥珀→红」单向渐进 | — | 见 C3-3 降级方案 |
| **P2** | 图与预览图尺寸/圆角/边距与 `preview` 不完全一致 | 轻微不齐 | 统一 `--radius-md` + 同宽 |

---

#### A1-6 移动端（375px，目标用户主战场）

| 级别 | 问题 | 当前观感 | 期望观感 |
|---|---|---|---|
| **P0** | 多按钮高度 < 44px：`demo-btn` 约 30px、`modal-btn` 约 41px、`summary` 行高 < 44px | 单手点击容易点空 | 所有可点元素 ≥ 44×44（`--tap-min`） |
| **P1** | `hero` `padding:44px` + `h1:34px` 固定值，375px 下标题占比过大，首屏被 Hero 占满，看不到上传区 | 「要滚一下才看得到该干嘛」 | 移动端 Hero 压缩（`h1:28px`、上下 padding 24px），保证首屏露出 dropzone 顶部 |
| **P1** | `main{width:min(720px,92vw)}` 在 375px 下 = 345px，卡片 `padding:28px` 后内容仅 289px，`hint` 两行文字挤压 | 边缘局促 | 移动端卡片 padding 降至 16px，`main` 用 `100% - 32px` |
| **P1** | 结果区在页面上方内容之后，出结果后**需要手动滚动**才能看到 | 演示时讲完话结果在屏幕外 | 出结果后自动 `scrollIntoView` 到结论卡（行为建议，非强改） |
| **P2** | 无 `prefers-reduced-motion`，弹窗有 `0.25s/0.3s` 动画 | 动效不可控 | 见 B6 |

---

### A2. 问题分级汇总

| 级别 | 数量 | 主题 |
|---|---|---|
| **P0** | 11 | ①阻塞弹窗+emoji ②合规标注位置 ③空状态无引导 ④示例按钮权重低 ⑤结果无结论卡 ⑥热力图被埋 ⑦技术指标直出 ⑧热力图无图例 ⑨触摸目标 <44px ⑩logo 资产 0 使用 ⑪焦点/键盘缺失 |
| **P1** | 13 | 信息层级、字号/对比度、移动端挤压、处方平铺、分组语义等 |
| **P2** | 8 | 圆角超限、字重档位、字距、动效、数字对齐等 |

---

## B. 设计系统（可直接落地）

**设计寄存器判定：Product Register（产品型）** —— 本产品是「工具/仪器」，不是营销页。设计服务产品，标杆是「赢得熟悉感」。
**平台轴：responsive web，mobile-first**（目标用户 90% 用手机）。
**三轴刻度标定：`DESIGN_VARIANCE = 4`（克制偏移，不追混沌）/ `MOTION_INTENSITY = 3`（仅功能动效）/ `VISUAL_DENSITY = 5`（日常应用密度）**。

> 三轴理由：演示场景下「可预测」>「炫技」。任何需要评委重新学习的布局都是负分。

### B1. 色板（以现有 `:root` 为起点扩展，不推翻）

**原则**：中性色 70–90% / 强调色 5–10% / 语义色 0–5%。现有 8 个变量全部保留为「别名（B-slot）」指向新语义层，前端无需改现有选择器即可平滑迁移。

| 语义 Token | 值 | 来源/理由 |
|---|---|---|
| `--bg` | `#F5F9F6` | 保留现有冷绿白基调（**故意不用奶油/米色暖中性**，避免「AI 默认暖色」） |
| `--surface` | `#FFFFFF` | 原 `--card-bg` |
| `--surface-sunken` | `#F8FAFC` | 原硬编码 `#f8fafc` 提级为 token |
| `--surface-tint` | `#FBFDFC` | 原 `#fbfdfc` |
| `--fg` | `#1F2933` | 原 `--ink` |
| `--fg-2` | `#475569` | 次级正文（7.5:1） |
| `--muted` | `#64748B` | 原 `--muted`，仅用于 ≥12px 元信息（4.76:1） |
| `--line` | `#E2E8F0` | 原 `--line` |
| `--line-strong` | `#CBD5E1` | 输入框/拖拽区 |
| `--border-soft` | `#F1F5F9` | 行分隔 |
| **`--accent`** | `#2E7D4F` | **保留原 `--green`**（品牌主绿，白底 4.9:1） |
| `--accent-strong` | `#1F5E3A` | 原 `--green-dark`，hover/标题 |
| `--accent-soft` | `#EAF5EE` | 原 `--green-light` |
| `--accent-on` | `#FFFFFF` | accent 底上的前景 |
| `--accent-graphic` | `#22C55E` | 与 logo 一致的亮绿，**仅用于大尺寸图形/logo，禁止用于文字** |
| **`--teal`** | `#0E7490` | **取自 logo 虹膜**，作为「AI/识别」语义色（差异化于竞品绿/蓝） |
| `--teal-soft` | `#ECFEFF` | 青色浅底 |
| `--success` | `#15803D` | 健康 |
| `--success-soft` | `#E7F5EC` | |
| `--warn` | `#B45309` | 替代原 `#8a6d3b`（白底 5.1:1，达 AA） |
| `--warn-soft` | `#FEF6E7` | 替代原 `#fff9e6` |
| `--warn-line` | `#F0D9A8` | |
| `--danger` | `#B42318` | 替代原 `#c0392b`（6.0:1，字号小也安全） |
| `--danger-soft` | `#FDECEA` | 替代原 `#f1f5f9` + `#a32d2d` 混用 |
| `--info` | `var(--teal)` | |
| **热力图图例相关** | `--heat-low: #2E7D4F` / `--heat-mid: #F2C14E` / `--heat-high: #B42318` | 图例条用，见 C3-3 |

> 用法铁律：**每屏可见的 `--accent` 使用 ≤2 处**。青色 `--teal` 仅用于「AI 识别」相关（徽标、图例说明、技术详情），不用于按钮。

### B2. 间距刻度（4px 基准网格，仅允许这些值）

```css
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 20px;  --space-6: 24px;  --space-8: 32px;  --space-10: 40px;
--space-12: 48px; --space-16: 64px; --space-20: 80px;
```

### B3. 圆角刻度

```css
--radius-xs: 6px;    /* 小标签、图例 */
--radius-sm: 8px;    /* 按钮、输入框 */
--radius-md: 12px;   /* 内层卡、图片 */
--radius-lg: 16px;   /* 外卡片上限（禁用 ≥24px） */
--radius-pill: 9999px;
```

### B4. 字号 / 字重 / 行高（**字重仅 400 与 500 两档**）

```css
/* 字号阶梯 */
--text-xs: 12px;  --text-sm: 13px;  --text-base: 16px; /* 正文基准 */
--text-md: 18px;  --text-lg: 20px;  --text-xl: 24px;
--text-2xl: 30px; --text-3xl: 38px;

/* 行高 */
--leading-tight: 1.25;  /* 标题 */
--leading-snug: 1.5;
--leading-body: 1.7;    /* 中文正文 */

/* 字距 */
--tracking-tight: -0.02em; /* ≥24px 标题 */
--tracking-normal: 0;      /* 正文 */
--tracking-caps: 0.06em;   /* 全大写/全角标签 */

/* 字重 —— 仅两档 */
--fw-normal: 400;
--fw-medium: 500;
```

**字重迁移对照（现有代码需改）**：`font-weight:300 → 400`；`600 → 500`；`700 → 500`。层级靠**字号 + 颜色**建立，而非字重堆叠。

### B5. 阴影层级（**同时修复「幽灵卡片」违规**）

```css
--elev-0: none;
--elev-1: 0 1px 2px rgba(16, 24, 40, 0.05);                          /* 行/轻微抬升 */
--elev-2: 0 1px 2px rgba(16, 24, 40, 0.05), 0 4px 8px rgba(31,94,58,0.05); /* 卡片 */
--elev-3: 0 12px 32px rgba(15, 60, 40, 0.16);                        /* 弹窗（无边框）*/
```

> 规则：**同一元素不得同时出现 `1px border` 与 `blur ≥ 16px` 阴影**。现有 `.upload-card` 是 `1px --line` + `0 8px 30px`（blur 30）= 幽灵卡片，改为 `1px --line` + `--elev-2`（blur ≤ 8）。

### B6. 动效（时长与缓动）

```css
--motion-fast: 120ms;  /* 按下/切换 */
--motion-base: 180ms;  /* hover / 进入 */
--motion-slow: 280ms;  /* 弹窗 / 面板 */
--ease-standard: cubic-bezier(0.2, 0, 0, 1);
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);
--z-modal: 1000;
--tap-min: 44px;
--focus-ring: 0 0 0 3px rgba(46, 125, 79, 0.35);
--focus-offset: 2px;
```

**必须补的无障碍基线**（当前代码完全缺失）：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
:where(a, button, summary, [tabindex], input, .dropzone):focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: var(--focus-offset);
  box-shadow: var(--focus-ring);
  border-radius: inherit;
}
```

### B7. 图标系统规范（P0 锁定）

**选型：`Lucide`（lucide.dev）—— 锁定唯一一套，全站不混用。**

选型理由（针对本项目约束逐条验证）：
- **可离线内联**：Lucide 每个图标就是一段 `<svg>` 路径源码，直接复制粘贴进 HTML，**不依赖 CDN、不依赖 JS**，符合「无构建」约束，且演示断网也不会挂。
- **几何统一**：单一 `24×24` 网格、`stroke-width: 2`、`round` 线帽/线接，40+ 图标放一起不会「粗细不一」。
- **协议**：ISC 许可，可商用。
- **禁用项**：Feather（已由 Lucide 接棒、维护弱）、Heroicons（两套风格易混用）、Font Awesome（体量重、需 CDN/字体文件）。

**内联模板（统一，禁止改动 `viewBox`/`stroke` 语义）**：

```html
<!-- 尺寸 24（独立图标）/ 20（按钮内）/ 16（行内），仅改 width/height -->
<svg class="icon" width="24" height="24" viewBox="0 0 24 24" fill="none"
     stroke="currentColor" stroke-width="2" stroke-linecap="round"
     stroke-linejoin="round" aria-hidden="true"><!-- lucide path --></svg>
```

- 尺寸：**16px（行内）/ 20px（按钮内）/ 24px（独立）**，全项目仅此三档。
- `stroke-width`：24/20px 用 `2`；16px 用 `1.75`（光学补偿，避免小尺寸糊成一团）。
- 颜色一律 `stroke="currentColor"`，由父级 `color` 控制 → 天然走 token。
- 装饰性图标必须 `aria-hidden="true"`；独立语义图标用 `aria-label`。

**本项目所需图标清单（13 个）**：

| 用途 | Lucide 名 | 尺寸 | 语义 |
|---|---|---|---|
| 上传照片 | `upload-cloud` | 40 / 24 | 主上传入口 |
| 拍照/相机 | `camera` | 16 | 拍摄规范提示 |
| 示例图 | `image` | 20 | 「上传示例病叶图」按钮内 |
| 展开箭头 | `chevron-down` | 16 | `<details>` 摘要（用 CSS `rotate` 表示展开态） |
| 关闭 | `x` | 20 | 弹窗关闭 |
| 警告 | `alert-triangle` | 20 | 灰色地带警告条 |
| 合规/成功 | `check-circle` | 16 | 合规标注、成功态 |
| 病灶定位 | `crosshair` | 20 | 热力图区块标题 |
| 技术详情 | `info` | 16 | 「分布相似度」折叠入口 |
| 作物/品牌 | `sprout` | 24 | 品牌辅助（**优先用 `logo_icon.svg`**） |
| 生物防治 | `shield-check` | 20 | 处方区块 |
| 化学用药 | `flask-conical` | 20 | 处方区块 |
| 日常管理 | `calendar-check` | 20 | 处方区块 |
| 严重程度 | `activity` | 20 | 结论卡严重程度 |
| 加载中 | `loader` | 24 | 识别中（`animate: spin`） |
| 空/失败 | `image-off` | 40 | 无结果空状态 |
| 重拍 | `rotate-ccw` | 20 | 失败重试 |

> 注意：`chevron-down` 自 Spread 图标展开态用 CSS `transform: rotate(180deg)` 实现，不引入第二套图标。
> **禁止**：任何 emoji 字符（如 `U+1F33E` 稻穗 / `U+1F680` 火箭 / `U+2728` 闪亮 / `U+1F525` 火焰）、任何图标字体（Font Awesome / iconfont）、任何第二套 SVG 库。

### B8. 完整 Token 定义（可直接替换现有 `:root` 块）

```css
:root {
  /* ===== A1-identity：品牌色 ===== */
  --accent: #2E7D4F;
  --accent-strong: #1F5E3A;
  --accent-soft: #EAF5EE;
  --accent-on: #FFFFFF;
  --accent-graphic: #22C55E;   /* 仅图形，禁用于文字 */
  --teal: #0E7490;             /* AI/识别语义色，取自 logo 虹膜 */
  --teal-soft: #ECFEFF;

  --bg: #F5F9F6;
  --surface: #FFFFFF;
  --surface-sunken: #F8FAFC;
  --surface-tint: #FBFDFC;

  --fg: #1F2933;
  --fg-2: #475569;
  --muted: #64748B;

  --line: #E2E8F0;
  --line-strong: #CBD5E1;
  --border-soft: #F1F5F9;

  /* ===== A2：语义色 ===== */
  --success: #15803D;
  --success-soft: #E7F5EC;
  --warn: #B45309;
  --warn-soft: #FEF6E7;
  --warn-line: #F0D9A8;
  --danger: #B42318;
  --danger-soft: #FDECEA;
  --info: var(--teal);

  /* 热力图图例 */
  --heat-low: #2E7D4F;
  --heat-mid: #F2C14E;
  --heat-high: #B42318;

  /* ===== 字体 ===== */
  --font-body: "Inter", "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei",
               "Noto Sans SC", "Source Han Sans SC", system-ui, sans-serif;
  --font-display: var(--font-body);
  --font-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Consolas, monospace;

  --text-xs: 12px;  --text-sm: 13px;  --text-base: 16px; --text-md: 18px;
  --text-lg: 20px;  --text-xl: 24px;  --text-2xl: 30px;  --text-3xl: 38px;
  --leading-tight: 1.25; --leading-snug: 1.5; --leading-body: 1.7;
  --tracking-tight: -0.02em; --tracking-normal: 0; --tracking-caps: 0.06em;
  --fw-normal: 400; --fw-medium: 500;

  /* ===== 间距 / 圆角 ===== */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-10: 40px;
  --space-12: 48px; --space-16: 64px; --space-20: 80px;
  --radius-xs: 6px; --radius-sm: 8px; --radius-md: 12px;
  --radius-lg: 16px; --radius-pill: 9999px;

  /* ===== 阴影 / 动效 ===== */
  --elev-0: none;
  --elev-1: 0 1px 2px rgba(16, 24, 40, 0.05);
  --elev-2: 0 1px 2px rgba(16, 24, 40, 0.05), 0 4px 8px rgba(31, 94, 58, 0.05);
  --elev-3: 0 12px 32px rgba(15, 60, 40, 0.16);
  --motion-fast: 120ms; --motion-base: 180ms; --motion-slow: 280ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --focus-ring: 0 0 0 3px rgba(46, 125, 79, 0.35);
  --focus-offset: 2px;
  --z-modal: 1000;
  --tap-min: 44px;

  /* ===== 布局 ===== */
  --container-max: 720px;
  --gutter: 20px;
  --section-y: 32px;

  /* ===== B-slot 兼容别名（旧变量名继续可用，无需改现有选择器） ===== */
  --green: var(--accent);
  --green-dark: var(--accent-strong);
  --green-light: var(--accent-soft);
  --ink: var(--fg);
  --card-bg: var(--surface);
}
```

**机器可读 `design-tokens.json`**（前端可直接 `import`，供 Token 校验与后续复用）：

```json
{
  "color": {
    "accent":          { "value": "#2E7D4F", "type": "color" },
    "accentStrong":    { "value": "#1F5E3A", "type": "color" },
    "accentSoft":      { "value": "#EAF5EE", "type": "color" },
    "accentGraphic":   { "value": "#22C55E", "type": "color" },
    "teal":            { "value": "#0E7490", "type": "color" },
    "bg":              { "value": "#F5F9F6", "type": "color" },
    "surface":         { "value": "#FFFFFF", "type": "color" },
    "surfaceSunken":   { "value": "#F8FAFC", "type": "color" },
    "fg":              { "value": "#1F2933", "type": "color" },
    "fg2":             { "value": "#475569", "type": "color" },
    "muted":           { "value": "#64748B", "type": "color" },
    "line":            { "value": "#E2E8F0", "type": "color" },
    "success":         { "value": "#15803D", "type": "color" },
    "warn":            { "value": "#B45309", "type": "color" },
    "danger":          { "value": "#B42318", "type": "color" },
    "heatLow":         { "value": "#2E7D4F", "type": "color" },
    "heatMid":         { "value": "#F2C14E", "type": "color" },
    "heatHigh":        { "value": "#B42318", "type": "color" }
  },
  "font": {
    "familyBody": { "value": "Inter, PingFang SC, HarmonyOS Sans SC, Microsoft YaHei, Noto Sans SC, system-ui, sans-serif", "type": "fontFamily" },
    "familyMono": { "value": "JetBrains Mono, ui-monospace, Consolas, monospace", "type": "fontFamily" },
    "size": {
      "xs":   { "value": "0.75rem", "type": "dimension" },
      "sm":   { "value": "0.8125rem", "type": "dimension" },
      "base": { "value": "1rem", "type": "dimension" },
      "md":   { "value": "1.125rem", "type": "dimension" },
      "lg":   { "value": "1.25rem", "type": "dimension" },
      "xl":   { "value": "1.5rem", "type": "dimension" },
      "2xl":  { "value": "1.875rem", "type": "dimension" },
      "3xl":  { "value": "2.375rem", "type": "dimension" }
    },
    "weight": { "normal": { "value": 400, "type": "number" }, "medium": { "value": 500, "type": "number" } }
  },
  "space": {
    "1": { "value": "4px", "type": "dimension" }, "2": { "value": "8px", "type": "dimension" },
    "3": { "value": "12px", "type": "dimension" }, "4": { "value": "16px", "type": "dimension" },
    "5": { "value": "20px", "type": "dimension" }, "6": { "value": "24px", "type": "dimension" },
    "8": { "value": "32px", "type": "dimension" }, "10": { "value": "40px", "type": "dimension" }
  },
  "radius": {
    "xs": { "value": "6px", "type": "dimension" }, "sm": { "value": "8px", "type": "dimension" },
    "md": { "value": "12px", "type": "dimension" }, "lg": { "value": "16px", "type": "dimension" },
    "pill": { "value": "9999px", "type": "dimension" }
  },
  "shadow": {
    "elev1": { "value": "0 1px 2px rgba(16,24,40,0.05)", "type": "boxShadow" },
    "elev2": { "value": "0 1px 2px rgba(16,24,40,0.05), 0 4px 8px rgba(31,94,58,0.05)", "type": "boxShadow" },
    "elev3": { "value": "0 12px 32px rgba(15,60,40,0.16)", "type": "boxShadow" }
  },
  "motion": {
    "fast": { "value": "120ms", "type": "duration" },
    "base": { "value": "180ms", "type": "duration" },
    "slow": { "value": "280ms", "type": "duration" },
    "easeStandard": { "value": "cubic-bezier(0.2,0,0,1)", "type": "cubicBezier" }
  },
  "layout": {
    "containerMax": { "value": "720px", "type": "dimension" },
    "tapMin": { "value": "44px", "type": "dimension" }
  }
}
```

### B9. 组件规范（含完整状态矩阵）

**Button / 次级按钮**（`.btn` / `.btn-secondary`）

| 状态 | 规格 |
|---|---|
| Default | 高 `44px`，`padding: 0 var(--space-4)`，`radius: var(--radius-sm)`，`fw: var(--fw-medium)`，主按钮 `bg: var(--accent); color: var(--accent-on)`；次按钮 `bg: transparent; border: 1px solid var(--accent); color: var(--accent)` |
| Hover | 主 `bg: var(--accent-strong)`；次 `bg: var(--accent-soft)`；过渡 `var(--motion-base) var(--ease-standard)` |
| Focus | `:focus-visible` → `outline: 2px solid var(--accent); outline-offset: 2px` |
| Active | `transform: translateY(1px)`；主 `bg: color-mix(in srgb, var(--accent) 88%, black)` |
| Disabled | `opacity: 0.5; cursor: not-allowed; pointer-events: none`（**不能用 opacity:0.6 后仍可点**，现 `demo-btn:disabled` 即此问题） |
| Loading | 左侧 `loader` 图标 16px `spin`，文案改「识别中…」，`aria-busy="true"`，禁用点击 |
| Error | 按钮本身不承载错误，错误由 `.alert` 条承担 |

**Dropzone**：Default（`border: 2px dashed var(--line-strong)`）→ Dragover（`border-color: var(--accent); background: var(--accent-soft)`，**由 class 控制，禁止内联 style**）→ Loading（骨架/`loader` 旋转 + 「正在校验图片…」）→ Success（缩略图预览替换 dropzone 内文案）→ Error（`--danger` 描边 + 说明 + 「重拍」按钮）→ Disabled（不适用，始终可点）。

**Result Verdict Card（新增）**：Default（有病结论）→ Healthy（`--success` 色标 + 「叶片健康，未发现明显病害」）→ Low-confidence（`--warn` 色标 + 「建议重拍」）→ Rejected/OOD（`--danger` 色标 + 拒识说明 + 原始判定折叠）。

**Detection Row / Prescription Block / Alert / Empty**：均按 `Default / Hover(仅可交互项) / Focus / Disabled(不适用) / Loading / Error / Empty / Edge` 覆盖；`Edge` 需处理**超长病名**（`word-break: break-word` + 两行截断 + `title` 全称）与**置信度 100.0%** 的宽度。

---

## C. 国奖级视觉改造方案

### C1. 主视觉方向

**方向名：「田间仪器（Field Instrument）」**

**对标参照**：Stripe（数据表达的严谨与克制）+ Notion（信息组织的清晰）+ 农业传感设备的工程仪表面板感。
**明确不追求**：竞品「智驭未来队」那种「大而全云平台后台」。它证明了一件事 —— **覆盖面不是这个赛道的评分点，可解释性与易用性才是**。我们反其道而行：单页、极简、一条闭环做到极致。

**人格定位（双受众平衡）**：
- 对**评委**：专业、可验证、每一项结论都有证据（热力图）与不确定性边界（可信度分级、拒识机制）。
- 对**农户**：不吓人、不必先懂术语、三步就能用（拍 → 看 → 照做）。

**配色基调**：以**叶绿 `--accent #2E7D4F`** 为唯一主色（保留现有品牌绿），以 **logo 虹膜青 `--teal #0E7490`** 作为「AI 识别」的语义辅色 —— 这一绿一青的组合**同时区别于竞品的纯绿**和**全行业滥用的后台蓝**，且**来自自有 logo，不是拍脑袋选的**。中性底保持冷绿白 `#F5F9F6`（**刻意避开奶油/米色暖中性**）。
色彩配比：中性 82% / 绿 12% / 青 4% / 语义色 2%。

**字体策略**：`Inter`（拉丁与数字，等宽数字 `tnum`）+ 系统中文字体栈（`PingFang SC` / `HarmonyOS Sans SC` / `Microsoft YaHei`），**默认不依赖网络加载字体** —— 演示现场网络不可控，系统字体栈是零风险方案；`Noto Sans SC` 仅作已安装时的回退。字重仅 **400 / 500** 两档。等宽 `JetBrains Mono` 用于置信度与相似度数值（技术感的来源，用在这里而非标题）。

**整体气质**：白底、细线、大留白、结论先行；不用渐变做装饰（唯一允许的渐变是热力图图例条）；圆角不超过 16px；阴影极浅。

### C2. 信息架构重组方案（三段式叙事：识别 → 定位 → 处方）

**评委 3 分钟应该看到的三件事（按优先级）**：
1. **这是什么病、准不准**（结论卡，0 秒可见）
2. **你凭什么说是这个病**（热力图，「看得见病灶」= 对竞品的降维打击）
3. **所以我该怎么办**（三段处方，落地价值）

**桌面（≥768px）线框图**：

```text
┌──────────────────────────────────────────────────────────┐
│ [logo] 禾目 AgriGuard                    [ AI 辅助制作 ] │  ← 顶部条：品牌左，合规右
├──────────────────────────────────────────────────────────┤
│                                                          │
│  禾目 AgriGuard                                          │  ← Hero 左对齐（非居中）
│  拍一张病叶照片，自动识别作物与病害，给出防治处方           │     右侧 96px logo_icon
│                                                          │
│  ┌── 第 1 步 · 拍摄 ───────────────────────────────┐      │
│  │   [upload-cloud 40px]                            │      │
│  │   点击或拖拽上传病叶照片                          │      │
│  │   拍摄规范：  [camera]单片  [square]纯色底  [arrow]正上方│      │
│  │   ┌──────────┐  拍成这样：                       │      │
│  │   │ 示例缩略图 │  [ 使用示例病叶图 ]  ← 演示主入口 │      │
│  │   └──────────┘                                  │      │
│  └─────────────────────────────────────────────────┘      │
│   不用先判断是什么作物 —— 14 种作物自动识别  [ chevron ▸ ] │
│                                                          │
│  ┌── 第 2 步 · 诊断结论 ───────────────────────────┐      │
│  │  番茄 · 早疫病                                    │      │  ← 24px/500，结论即标题
│  │  [可信度 高 92%]  [activity 严重程度：中度]        │      │  ← 语义色胶囊
│  │  叶片出现同心轮纹病斑，边缘黄化……                 │      │  ← 一句话人话
│  │  ▸ 其他可能（2）        ▸ 技术详情（相似度 0.43） │      │  ← 折叠，评委可展开
│  └─────────────────────────────────────────────────┘      │
│                                                          │
│  ┌── 第 3 步 · 病灶定位 ───────────────────────────┐      │
│  │  [crosshair] 模型注意力可视化                      │      │
│  │  ┌───────────────────────────────────────────┐  │      │
│  │  │            热力图（病灶高亮）               │  │      │
│  │  └───────────────────────────────────────────┘  │      │
│  │  关注度  低 ▁▂▃▅▆▇ 高     这是什么？ [ ▸ ]      │      │  ← 图例条 + 解释
│  └─────────────────────────────────────────────────┘      │
│                                                          │
│  ┌── 第 4 步 · 防治处方 ───────────────────────────┐      │
│  │  [shield-check] 生物防治    …                     │      │
│  │  [flask-conical] 化学用药   …                     │      │
│  │  [calendar-check] 日常管理  …                     │      │
│  └─────────────────────────────────────────────────┘      │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  智慧农业 · 减肥减药 · 数字乡村   |   AI 辅助制作          │  ← 合规二次落位
└──────────────────────────────────────────────────────────┘
```

**移动端（375px）差异**：
- Hero 压缩（`h1: 28px`，上下 `var(--space-6)`），logo 缩小为 40px 内联在标题左侧。
- 单列全宽；卡片 `padding: var(--space-4)`；`main{ width: 100%; padding: 0 var(--space-4) }`。
- 拍摄规范三要点改为**竖排**（图标 + 文字一行一个）。
- 所有按钮 ≥ `44px`；`示例病叶图` 按钮在首屏内可见（**演示时单手可点**）。
- 出结果后 `scrollIntoView` 到结论卡。
- 热力图图例条宽度 100%，不换行。

### C3. 高 ROI 视觉增强项（最多 3 个）

#### 增强项 1：诊断结论卡（Diagnosis Verdict Card）

- **预期观感提升**：从「一页技术参数」变成「一张病历单」。评委 0.5 秒获得「**是什么病 / 多准 / 多严重**」三要素，产品故事立住。
- **实现要点**：
  - 位置：`#result` 内 `#detections` 之前新增 `.verdict` 容器。
  - 数据来源**全部为现有字段**，无需改后端：`data.detections[0].name`（病名）、`.confidence`（可信度）、`data.prescription.severity`（严重程度）、`data.prescription.summary`（一句话）。
  - 可信度映射（人话化，**不暴露阈值术语**）：`conf ≥ 0.85` → 「高」`--success`；`0.6 ≤ conf < 0.85` → 「中」`--warn`；`< 0.6` → 「低」`--danger`。原值以 12px 等宽数字**同胶囊内**呈现（农户看字、评委看数，一次满足）。
  - 严重程度色标：`健康`→ `--success`；`轻/初期`→ `--warn`；`中/重/严重`→ `--danger`。
  - Top3 的 rank2/3 移入 `其他可能（N）` `<details>`；相似度原值移入 `技术详情 ▸` `<details>`。
- **工作量**：M（改 `render()` 约 40 行 + 新增 ~50 行 CSS）。
- **风险**：`severity` 文案自由文本，色标匹配需容错 → 用「包含关键词」匹配，未命中则回落中性色。
- **降级方案**：若工时紧张，仅把 `detections` 第一行改为「病名 + 可信度」大字，其余不动（15 分钟可完成）。

#### 增强项 2：拍摄规范引导卡（替代欢迎弹窗）

- **预期观感提升**：省掉演示第 0 次点击；空状态从「一个加号」变成「照着做就行」；同时把品牌 logo 带进页面。
- **实现要点**：
  - 移除阻塞式 `modal-overlay`（或改为默认 `hidden` + 顶部 `?` 按钮触发，`Esc` 可关、`role="dialog"` + `aria-modal="true"` + 焦点陷阱）。
  - 规范以三段常驻内联呈现（图标 16px + 文字 13px）：`单片叶片` / `纯色背景` / `正上方拍摄`。
  - 复用 `_demo_leaf_compliant.jpg` 作为 80×80 缩略图 + 「使用示例病叶图」按钮并排，形成「照这样拍 → 或直接用示例」的**双入口**。
- **工作量**：S–M。
- **风险**：示例图 404 时出现破图 → `onerror` 隐藏缩略图并回退为纯文字。
- **降级方案**：不引缩略图，仅保留图标 + 三行规范 + 提升示例按钮权重（纯 CSS，10 分钟）。

#### 增强项 3：热力图图例 + 人话解释

- **预期观感提升**：把「一堆彩虹色」变成「可读的证据」。这是对竞品「只有检测框」的正面碾压，也是抽检时最容易被追问的点 —— 答得上来就是加分。
- **实现要点**：
  - 热力图上方加图例条：`关注度 低 [渐变条] 高`，渐变用 `linear-gradient(90deg, var(--heat-low), var(--heat-mid), var(--heat-high))`，高 `6px`，`--radius-pill`。
  - 图例下加一行 12px `--muted` 说明：「颜色越暖，表示模型越关注的病斑区域，不代表严重程度」。
  - `这是什么？ ▸` 折叠一段 60 字解释：Grad-CAM 通过梯度反传定位模型判据区域，用于验证结论可解释性。
  - 区块标题由「病灶定位」升级为「模型注意力可视化」+ `crosshair` 图标（技术感 + 准确表述）。
  - **色盲友好补充**：在热力图右侧保留一张**原图小尺寸对照**（可选），或提供「原图 / 热力图」切换开关 —— 不依赖颜色也能比对。
- **工作量**：S（纯 CSS + 少量 DOM）。
- **风险**：后端若使用 JET 色带，「红=高关注」与图例的「红=高」一致，但色盲用户仍可能难辨蓝/绿 → 见降级。
- **降级方案**：若后端色带可改（需与 backend 协调），改用**单向渐进**（青 → 琥珀 → 红，或 viridis）；若不可改，仅保留图例条与文字说明，并**额外提供原图并排**，确保不依赖色相也能读懂。

### C4. 答辩演示视角：最佳演示路径

**目标路径（1 次点击、3 秒出结果）**：

```text
① 打开页面
   → 首屏即见：品牌 + 一句产品定义 + 上传入口 + 示例按钮
② 点击「使用示例病叶图」   ← 唯一一次点击
   → 演示主入口必须是首屏内、≥44px、视觉权重最高的按钮
③ 3 秒内出结论卡：番茄 · 早疫病 ｜ 可信度 高 92% ｜ 严重程度 中度
④ 指热力图讲差异化：「竞品只能给你一个框，我们告诉你模型看的是病斑的哪里」
⑤ 指三段处方讲落地：「生物防治优先、化学用药给到具体药剂、日常管理可执行」
⑥ 展开「技术详情」与「其他可能」讲严谨：「我们还有拒识机制，看不懂的图会拒答而不是硬猜」
```

**当前流程中拖慢/干扰这条路径的设计点**：

| 干扰点 | 影响 | 处置（对应本方案） |
|---|---|---|
| 欢迎弹窗阻塞（多 1 次点击 + 5 秒阅读 + 遮首屏） | 演示开局就卡顿 | 降级为可选帮助，规范内联（增强项 2） |
| 「上传示例病叶图」按钮过小（约 30px）且为浅绿底 | 演示时可能点空 | 提升为 44px 次级主按钮（增强项 2） |
| 结果区第一行是 `分布相似度 0.43` | 讲第一句话时评委看到的是天书 | 结论卡置顶，相似度折叠（增强项 1） |
| 热力图在 Top3 列表之后 | 最有说服力的证据要滚动才看到 | 热力图紧跟结论卡（C2 顺序） |
| 结果区无骨架屏，加载中只有一行文字 | 3 秒等待像「卡死了」 | 加 `loader` + 骨架，`aria-busy` |
| OOD 拒识分支是一块灰底小字 | 万一示例图被拒识，演示当场解释不清 | 拒识态改为 `--danger` 色标卡片 + 明确「为什么拒识」+ 重拍建议 |
| 出结果后需手动滚动 | 讲完话结果在屏幕外 | `scrollIntoView` 到结论卡 |
| 无 favicon | 投屏时标签页空白 | 加 `link rel="icon"` 指向 `logo_icon.svg` |

**演示防呆建议（供 devops/frontend 参考）**：示例图 `_demo_leaf_compliant.jpg` 必须**预先验证能过 OOD 阈值**（否则演示会出现拒识态）；建议在前端内置第 2、3 张备用示例图轮换。

---

## D. 合规校验

| 校验项 | 结论 | 说明 |
|---|---|---|
| 双盲要求（无学校名/单位名/指导老师姓名） | **通过** | 已通读 `index.html` / `app.js` / `styles.css` 全部可见文案，无任何学校、单位、导师姓名。页脚「智慧农业 · 减肥减药 · 数字乡村」为政策口号，合规。改造方案中亦未引入任何机构标识 |
| `AI 辅助制作` 合规标注保留 | **通过** | 标注**不删除**，仅调整位置：由「Hero 第 1 视觉落点」改为「顶部条右对齐小胶囊 + 页脚二次落位」。可见性不降低，干扰性下降 |
| 无 emoji 图标 | **改造后通过** | 现状 `index.html:12` 存在 emoji 字符 `U+1F33E` 需替换（见 blocking）。本方案正文与所有图标清单**零 emoji 字符**，全部为 Lucide SVG 语义映射 |
| 无紫色→粉色渐变 | **通过** | 全站现有渐变仅 `--green → --green-dark`（绿色系，合规）。本方案唯一新增渐变为热力图图例条（绿→琥珀→红，语义必需，非装饰）。**明确禁止** Indigo→Pink 渐变 + 发光边框 + 毛玻璃组合 |
| 无硬编码色值 | **改造后通过** | 现状 `styles.css` 14 处、`app.js` 12 处硬编码需迁移至 token（见 blocking）。`design-tokens.json` 已产出于 B8 |
| 无空洞文案 | **通过（需替换 1 处）** | 现状「秒出诊断」为不可验证修饰词，建议改具体表述。方案文案全部为具体动作与可验证结果 |
| 无 `border-left` 色条强调 | **通过** | 本方案明确不用彩色左边框卡片，改 `1px` 边框 + hover 变 `--accent` |
| 无幽灵卡片 | **改造后通过** | 现状 `.upload-card` / `.result` 为 `1px border + blur 30px`，需改为 `--elev-2`（见 B5） |
| 卡片圆角 ≤16px | **改造后通过** | 现状 `.modal: 20px` 需降为 `--radius-lg: 16px` |
| 对比度 ≥4.5:1 | **改造后通过** | 现状 `#94a3b8` 文字（页脚、hint）约 2.6:1 不达标，改用 `--muted #64748B`（4.76:1） |
| 键盘可达 + `focus-visible` | **改造后通过** | 现状全站缺失，已给出统一 `:focus-visible` 规则（见 B6） |
| `prefers-reduced-motion` | **改造后通过** | 现状缺失，已给出规则（见 B6） |
| 触摸目标 ≥44×44px | **改造后通过** | 现状 `demo-btn` 约 30px、`summary` 行不足，需提升（见 A1-6） |
| 文案面向农户可理解 | **改造后通过（建议）** | 现状暴露「分布相似度 ≥0.32 为正常」，改为双层表达（增强项 1） |

---

## 交付与交接说明

本方案**未修改任何项目代码**（审查阶段），全部改造以「可复制片段」形式给出：

| 供给对象 | 交付内容 | 位置 |
|---|---|---|
| frontend | `:root` token 全文（可直接替换）、组件状态矩阵、图标内联模板与清单、三段式 HTML 结构线框 | 本文档 B1–B9、C2 |
| frontend | `design-tokens.json`（可 import） | 本文档 B8 |
| backend | 热力图色带建议（JET → 单向渐进），供色盲友好改造评估 | 本文档 C3-3 |
| team-lead | 改造优先级排序（P0 → P1）、A2 分级汇总 | 本文档 A2 |

**推荐落地顺序（按 ROI 排序）**：
1. 结论卡（增强项 1）—— 信息层级，收益最大
2. 拍摄规范卡替代弹窗 + 示例按钮升级（增强项 2）—— 演示路径，收益次之
3. 热力图图例（增强项 3）—— 差异化证明，成本最低
4. Token 迁移 + 无障碍基线（B6/B8）—— 一次性铺底，后续所有改动受益
5. 移动端断点与触摸目标修正（A1-6）

---

```text
verdict: fail

blocking:
  - 违反项: 团队 P0-1「禁止 emoji 作为 UI 功能图标」
    证据: frontend/index.html:12  `<div class="modal-badge">` + emoji 字符 U+1F33E（稻穗） + ` 禾目 AgriGuard</div>`
    期望: 替换为 `assets/logo_icon.svg` 内联（20px）或 Lucide `sprout` 语义图标；emoji 仅允许存在于用户生成内容中

  - 违反项: 团队红线 4「禁止硬编码色值，全部走 Design Token」
    证据: frontend/styles.css 第 18/32/68/87/102/108/118/141/167/191/229/246/259/294 行（如 `#f6fbf8`、`#edf5ef`、`#bfe0cc`、`#94a3b8`、`#d8eedf`、`#f8fafc`、`#fbfdfc`、`rgba(15,60,40,0.28)`）；frontend/app.js 第 101/106/117/145/152 行内联 style（`#64748b`、`#a32d2d`、`#f1f5f9`、`#475569`、`#8a6d3b`、`#fff9e6`）
    期望: 迁移至 B8 给出的 token 集合（`:root` 完整定义 + `design-tokens.json`），组件一律以 `var(--x)` 引用

  - 违反项: 团队红线 7「必须有可访问交互：focus-visible、键盘可达、prefers-reduced-motion」
    证据: frontend/styles.css 全 316 行内不存在 `:focus-visible`、不存在 `prefers-reduced-motion` 媒体查询；`.dropzone`（第 67 行）为可点击元素但无键盘焦点样式
    期望: 引入 B6 给出的统一 `:focus-visible` 规则与 `prefers-reduced-motion` 降级规则；所有可交互元素键盘可达

advisory:
  - 建议项: 结果区置顶「诊断结论卡」（病名 + 人话可信度 + 严重程度 + 一句话结论），Top3 后两名与「分布相似度」原值折叠
    理由: 现状第一行是农户不可读的技术参数、差异化卖点在滚动区之外；结论先行可让评委 0.5 秒获得「是什么/多准/多严重」，直接服务 3 分钟读懂目标（增强项 1）
  - 建议项: 阻塞式欢迎弹窗降级为可选帮助，拍摄规范内联进上传区常驻
    理由: 弹窗为演示路径第 0 步，多 1 次点击 5 秒阅读且关闭后规范即丢失；内容有价值但载体应改变（增强项 2）
  - 建议项: 提升「上传示例病叶图」按钮为 44px 次级主按钮并置于首屏
    理由: 它是演示最高频入口，现状约 30px 浅绿底，存在点空风险且不达触摸目标标准
  - 建议项: 热力图增加图例条 + 人话解释 + 「这是什么」折叠，并考虑提供原图并排/切换
    理由: 现状 JET 彩虹色带对色盲不友好且无图例，红=病灶重并非自发认知；且热力图是相对竞品「只有检测框」的核心差异化证据，需要被解释清楚（增强项 3）
  - 建议项: 「分布相似度 ≥0.32 为正常」改为双层表达（农户看「可信度 高/中/低」，评委在「技术详情」看原值）
    理由: 直出技术阈值与「面向小农户」定位冲突，但不删原值可同时满足严格评审的技术说服力
  - 建议项: 激活品牌资产 —— 页面引入 `logo_icon.svg`（Hero 右侧 + favicon），并以 logo 虹膜青 `#0E7490` 作为 AI/识别语义辅色
    理由: 三份 logo 资产当前零使用；绿+青双色源自自有品牌，可同时区别于竞品纯绿与行业泛滥的后台蓝，零成本提升「有品牌意识」印象
  - 建议项: 修复「幽灵卡片」（`.upload-card`/`.result` 现为 `1px border + blur 30px`）与圆角超限（`.modal: 20px`）
    理由: 违反红线 9（同元素 1px 边框 + blur ≥16px）与卡片圆角上限 16px；改为 `--elev-2`（blur ≤8）与 `--radius-lg`
  - 建议项: 页脚与 hint 文字色由 `#94a3b8`（约 2.6:1）改为 `--muted #64748B`（4.76:1）
    理由: 现状不达 WCAG AA 4.5:1；hint 是拍摄规范，读不清等于没写
  - 建议项: 字重统一收敛为 400 / 500 两档，移除现有 300 / 600 / 700
    理由: 符合团队「字重仅 400/500」规范；层级改用字号与颜色建立，更克制、更专业
  - 建议项: 增加加载骨架屏与 `scrollIntoView`，并预先验证示例图可通过 OOD 阈值（并备 2 张备用图）
    理由: 3 秒等待无反馈易被误判为卡死；结果若在屏幕外或示例图被拒识，会直接影响巡展「现场演示效果」这一 50% 权重项
  - 建议项: `body` 全屏线性渐变（`#f6fbf8 → #edf5ef`）改为纯色 `--bg #F5F9F6`
    理由: 装饰性渐变在投屏/低色域设备上易出现色带；纯色更稳且降低渲染风险

evidence:
  - { artifact_ref: frontend/index.html, line: 12, 说明: modal-badge 使用 emoji 字符 U+1F33E（稻穗）作为品牌/功能标记，违反 P0-1 }
  - { artifact_ref: frontend/index.html, line: 22-26, 说明: Hero 为居中标题+副标题通用型，AI 辅助制作徽标位于 H1 正上方第一视觉落点，无品牌资产 }
  - { artifact_ref: frontend/index.html, line: 32-35, 说明: 空状态仅文本 `+` 与两行 12px 灰字，无图标、无示例参照，引导力不足 }
  - { artifact_ref: frontend/index.html, line: 41-44, 说明: 「当前可识别作物」为核心差异化卖点（无需先选作物）却折叠隐藏 }
  - { artifact_ref: frontend/index.html, line: 49-57, 说明: 结果区顺序为 detections → heatmap → prescription，热力图（核心差异化证据）被排在置信度列表之后 }
  - { artifact_ref: frontend/app.js, line: 146, 说明: 直接向用户输出「分布相似度：0.43（≥0.32 为正常）」，技术阈值直出，与面向小农户定位冲突 }
  - { artifact_ref: frontend/app.js, line: 100-111, 说明: OOD 拒识分支以灰底小字呈现（#f1f5f9/#475569），无视觉层级，演示异常场景时解释力弱 }
  - { artifact_ref: frontend/app.js, line: 117, 152, 说明: 内联 style 硬编码色值，违反 token 契约 }
  - { artifact_ref: frontend/app.js, line: 26-32, 说明: 拖拽态以 style.borderColor 硬编码 #2e7d4f，且 dragleave 恢复为 #bfe0cc 硬编码，状态机不一致 }
  - { artifact_ref: frontend/styles.css, line: 59-65, 说明: .upload-card/.result 为 1px border + 0 8px 30px，构成幽灵卡片（red line 9） }
  - { artifact_ref: frontend/styles.css, line: 87, 说明: .dropzone .hint 使用 #94a3b8（约 2.6:1），低于 WCAG AA 4.5:1 }
  - { artifact_ref: frontend/styles.css, line: 96-99, 说明: 示例按钮 padding 6px 14px、13px 字号，实际高度约 30px，低于 44px 触摸目标且为演示高频入口 }
  - { artifact_ref: frontend/styles.css, line: 240-249, 说明: .modal border-radius:20px 超出卡片圆角 16px 上限 }
  - { artifact_ref: frontend/styles.css, line: 294, 说明: .modal-btn 使用 linear-gradient(135deg, --green, --green-dark)；为绿色系合规渐变，但产品型界面建议改纯色 --accent }
  - { artifact_ref: frontend/styles.css, line: 316, 说明: 文件结束，全站无 :focus-visible、无 prefers-reduced-motion，无障碍基线缺失 }
  - { artifact_ref: assets/logo_icon.svg, line: 4-18, 说明: 品牌真实色系为叶绿 #86EFAC→#4ADE80 / #22C55E→#15803D + 青色虹膜 #06B6D4/#0E7490；三份 logo 资产在页面中零使用 }
  - { artifact_ref: assets/logo_full.svg, line: 21-22, 说明: 横版 logo 含「禾目」#166534 与「AgriGuard · 慧眼识农」#0E7490，确认青色为品牌第二主色 }
```
