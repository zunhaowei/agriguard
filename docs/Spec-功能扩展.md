# Spec — 前端功能扩展 v1.0

> 生成日期：2026-09-21
> 基于：用户 2026-09-21 需求 + `docs/工作交接.md` 当前状态 + `docs/项目审查与优化报告.html`
> 状态：**已锁定**（用户已确认四项关键选型）
> 本文档是**团队内部契约**：设计、开发、测试均以此为唯一依据。

---

## 1. 产品定义

- **一句话**：给农户用的"拍照即诊断"工具，本次补齐**账号体系、病害知识库、诊断历史、语音播报**四块能力，
  把"一次性工具"变成"可回访的服务"。
- **目标用户**：小农户 / 基层农技员（演示场景下为评委）。
- **核心问题**：原前端只有单一"上传→出结果"页面。用户无法留存诊断记录、无法查阅病害知识、
  结果只能看不能听，功能显得单薄。

---

## 2. MVP 范围（锁定）

| # | 功能 | 验收标准摘要 | 优先级 |
|---|---|---|---|
| F1 | 登录页（注册 + 登录，含内置演示账号） | 能注册、能登录、能登出、未登录访问受保护页会被引导 | P0 |
| F2 | 病例库（按作物分类 → 病害列表 → 例图 + 简介） | 14 种作物 / 38 个类别全部可浏览；每个类别有例图与病害简介 | P0 |
| F3 | 历史记录（持久化 + 查询 + 详情 + 删除） | 登录后诊断自动入库；可按作物筛选、按关键词搜索；未登录不报错只是不入库 | P0 |
| F4 | 语音朗读（播报结论） | 一键播报"作物+病害+严重度+处方摘要"；可停止；不支持时给出提示而非静默失败 | P0 |
| F5 | 界面优化美化 | 统一导航、加载态、空状态、错误提示、移动端适配 | P1 |

### 2.1 明确不做（Out-of-Scope — 锁定）

| 不做 | 原因 | 何时考虑 |
|---|---|---|
| 短信/邮箱验证码、找回密码 | MVP 无真实用户规模，成本远高于收益 | 有真实用户后 |
| 第三方登录（微信/QQ） | 需企业资质与备案，赛前不可行 | 产品化阶段 |
| 权限分级（管理员/普通用户） | 单角色够用 | 有运营需求后 |
| 云端同步 / 多端共享 | 与"本机离线演示"冲突（见 §10） | 演示后 |
| 诊断记录导出 PDF | 非核心 | v2 |
| 前端框架化（Vue/React） | 现有原生方案已够用，引入构建链会破坏"零构建、离线可跑" | 不计划 |

---

## 3. 技术架构（锁定）

| 层 | 技术 | 版本 | 锁定原因 |
|---|---|---|---|
| 后端 | FastAPI | 沿用 0.141.1 | 既有 |
| **数据库** | **SQLite（Python stdlib `sqlite3`）** | 随 Python 3.13.15 | **零新依赖**、离线可用、单文件易备份；3 张表规模无需 ORM |
| 密码存储 | stdlib `hashlib.pbkdf2_hmac`（SHA-256, 20 万轮 + 每用户随机 salt） | — | 避免引入 bcrypt/passlib 依赖 |
| 会话 | **数据库会话令牌**（`secrets.token_urlsafe(32)`，存 `sessions` 表，7 天过期） | — | 可登出即失效；无需额外加密库 |
| 前端 | 原生 HTML/CSS/JS，**多页面 + 共享脚本** | 无构建 | 保持"零构建、离线可跑"；避免单文件膨胀 |
| 语音 | **Web Speech API**（`window.speechSynthesis`，zh-CN） | 浏览器内置 | 离线、免费、零依赖 |
| 图标 | 沿用现有**描边 SVG** 方案（项目已锁定，禁止 emoji） | — | P0 规则 |

### 3.1 ⚠️ 不得引入的新依赖

后端**不新增任何 pip 依赖**。用 stdlib 完成：`sqlite3` / `hashlib` / `hmac` / `secrets` / `json` / `base64`。
理由：本项目依赖纪律严格（`ultralytics` 已锁死版本），
每加一个库都会抬高"换机器复现"的风险，而本次功能用 stdlib 完全够用。

---

## 4. 数据库表（锁定）

库文件：`data/agriguard.db`（`data/` 已在 `.gitignore` 中，**不得提交**）
初始化：应用启动时自动建表 + 播种演示账号（幂等）。

```sql
-- 用户
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    display_name  TEXT    NOT NULL DEFAULT '',
    password_hash TEXT    NOT NULL,          -- pbkdf2_hmac sha256, hex
    salt          TEXT    NOT NULL,          -- hex, 16 bytes
    is_demo       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL           -- ISO8601 UTC
);

-- 会话
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- 诊断历史
CREATE TABLE IF NOT EXISTS history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at          TEXT NOT NULL,
    class_key           TEXT,                -- PlantVillage 类别键，如 Tomato___Early_blight
    crop_cn             TEXT,
    disease_cn          TEXT,
    confidence          REAL,
    ood_score           REAL,
    is_ood              INTEGER NOT NULL DEFAULT 0,
    is_warning          INTEGER NOT NULL DEFAULT 0,
    severity_grade      TEXT,
    lesion_ratio        REAL,
    prescription_json   TEXT,                -- 处方结构化 JSON
    prescription_source TEXT,                -- llm | template
    rejected_reason     TEXT,                -- 被拒识时的原因（可选记录）
    thumb_original      BLOB,                -- 原图缩略图（最长边 ≤320px JPEG）
    thumb_heatmap       BLOB                 -- 热力图缩略图（同上）
);
CREATE INDEX IF NOT EXISTS idx_history_user_time ON history(user_id, created_at DESC);
```

**为什么缩略图存 BLOB 而不是存文件**：`uploads/` 有 24 小时惰性回收策略，
存文件会导致历史记录里的图**过一天就变空白**。存进 DB 才是持久的。

**演示账号**：用户名 `demo` / 密码 `demo1234` / `is_demo=1`，仅首次建库时播种。

---

## 5. API 端点清单（锁定）

统一前缀 `/api/v1`。认证方式：`Authorization: Bearer <token>`。

| Method | Path | 功能 | 认证 | 请求体 | 响应体 |
|---|---|---|---|---|---|
| POST | `/api/v1/auth/register` | 注册 | 否 | `{username, password, display_name?}` | `{ok, token, user:{id,username,display_name,is_demo}}` |
| POST | `/api/v1/auth/login` | 登录 | 否 | `{username, password}` | 同上 |
| POST | `/api/v1/auth/logout` | 登出 | **是** | — | `{ok}` |
| GET | `/api/v1/auth/me` | 当前用户 | **是** | — | `{ok, user}` |
| GET | `/api/v1/cases` | 病例库索引 | 否 | — | `{ok, crops:[{crop_key,crop_cn,count,classes:[{class_key,disease_cn,is_healthy}]}]}` |
| GET | `/api/v1/cases/{class_key}` | 单个病例详情 | 否 | — | `{ok, class_key, crop_cn, disease_cn, is_healthy, summary, symptoms[], prevention[], image_url}` |
| GET | `/api/v1/cases/image/{class_key}` | 病例例图 | 否 | — | `image/jpeg` |
| GET | `/api/v1/history` | 历史列表 | **是** | `?limit=20&offset=0&crop=&q=` | `{ok, total, items:[{id,created_at,crop_cn,disease_cn,confidence,severity_grade,has_thumb,is_ood}]}` |
| GET | `/api/v1/history/{id}` | 历史详情 | **是** | — | `{ok, item:{...含处方 JSON...}}` |
| GET | `/api/v1/history/{id}/thumb` | 缩略图 | **是** | `?kind=original\|heatmap` | `image/jpeg` |
| DELETE | `/api/v1/history/{id}` | 删除一条 | **是** | — | `{ok}` |
| POST | `/api/v1/history` | **手动**存一条（可选） | **是** | 同 history 字段 | `{ok, id}` |

### 5.1 `/api/v1/predict` 的改动（关键设计）

**保持向后兼容**：`/api/v1/predict` 与 `/predict` 的**签名与响应体不变**，
新增**可选**的 `Authorization` 头：

- **带有效 token** → 在返回结果的同时，**自动写入一条历史记录**（含缩略图）。
- **不带 / token 无效** → **正常诊断，只是不入库**（不报错、不中断）。

理由：① 现有 14 项回归测试**无需改动**；② 未登录也能用核心功能，降低门槛；
③ 演示时登录一次，之后每次诊断自动留痕。

### 5.2 响应体新增字段（追加，不破坏既有字段）

`PredictResponse` 追加：
- `history_id: int | null` —— 本次记录入库后的 id；未入库为 `null`
- `class_key: str | null` —— 命中的类别键（供前端跳转病例库）

---

## 6. 页面清单（锁定）

| 页面 | 文件 | 路由 | 核心内容 | 依赖 API |
|---|---|---|---|---|
| 诊断页（既有） | `index.html` | `/` | 上传 + 结果 + 热力图 + 处方 + **语音按钮** | `/predict`, `/meta` |
| 登录/注册页 | `login.html` | `/static/login.html` | 登录/注册切换、演示账号一键填充 | `/auth/*` |
| 病例库 | `cases.html` | `/static/cases.html` | 左侧作物列表 / 右侧病害卡片网格；点击看详情 | `/cases` |
| 病例详情 | `case.html?id=` | `/static/case.html` | 例图 + 病害简介 + 症状 + 防治要点 | `/cases/{key}` |
| 历史记录 | `history.html` | `/static/history.html` | 列表 + 筛选 + 搜索 + 详情弹层 + 删除 | `/history` |

**导航**：所有页面共用同一顶部导航（由 `frontend/layout.js` 注入），
未登录时显示"登录"，已登录显示用户名 + 登出；受保护页（history）未登录时跳转登录页。

---

## 7. 设计约束（沿用既有 Token，不新造一套）

- **颜色/间距/字号一律走 `styles.css` 的 CSS 变量**，不得硬编码（唯一例外 `#fff`/`#000`）。
- **图标**：仅用**描边 SVG**（`stroke="currentColor"`，`stroke-width="2"`，圆角端点），
  尺寸 16 / 20 / 24px。**禁止 emoji**（项目 P0 规则）。
- **禁止**紫色→粉色渐变；禁止弹跳缓动 `cubic-bezier(0.68,-0.55,0.265,1.55)`。
- **响应式**：≥1024 三栏/两栏，768–1023 两栏，<768 单栏；触控目标 ≥44px。
- **无障碍**：对话框用 `role="dialog"` + `aria-modal`；所有按钮有 `aria-label`；
  键盘可 Tab 到达、ESC 可关闭；`prefers-reduced-motion` 时禁用动效。
- **文案**：面向农户，讲人话。禁止 `Lorem ipsum` / `Welcome to Our App` 类占位。

---

## 8. 验收标准（EARS）

| 编号 | 场景 | EARS 验收标准 | 优先级 |
|---|---|---|---|
| AC-01 | 注册 | When 用户提交未占用的用户名与 ≥8 位密码，系统**必须**创建账号并直接登录 | P0 |
| AC-02 | 注册 | If 用户名已存在，系统**必须**返回明确提示且不创建账号 | P0 |
| AC-03 | 登录 | When 提交正确的演示账号 `demo`/`demo1234`，系统**必须**登录成功 | P0 |
| AC-04 | 登录 | If 密码错误，系统**必须**返回"用户名或密码错误"（不区分二者以免泄露账号是否存在） | P0 |
| AC-05 | 会话 | While 未携带或携带过期 token，访问 `/history`，系统**必须**返回 401 | P0 |
| AC-06 | 登出 | When 用户登出，系统**必须**使该 token 立即失效 | P0 |
| AC-07 | 病例库 | While 浏览病例库，系统**必须**列出全部 14 种作物的 38 个类别 | P0 |
| AC-08 | 病例详情 | When 打开任一病例，系统**必须**给出例图、病害中文名、简介与防治要点 | P0 |
| AC-09 | 历史入库 | When 已登录用户完成一次诊断，系统**必须**自动写入一条含缩略图的历史 | P0 |
| AC-10 | 历史入库 | When 未登录用户完成诊断，系统**必须**正常返回结果且不写入历史、不报错 | P0 |
| AC-11 | 历史查询 | When 按作物筛选或输入关键词，系统**必须**只返回匹配项 | P0 |
| AC-12 | 历史删除 | When 用户删除一条自己的记录，系统**必须**删除且不可再查询到 | P0 |
| AC-13 | 越权 | If 用户 A 请求用户 B 的历史 id，系统**必须**返回 404（不泄露存在性） | P0 |
| AC-14 | 语音 | When 点击朗读按钮，系统**必须**播报"作物+病害+严重度+处方摘要" | P0 |
| AC-15 | 语音降级 | If 浏览器不支持语音合成，系统**必须**给出可见提示而非静默失败 | P1 |
| AC-16 | 兼容 | While 运行既有 14 项回归测试，**必须**全部通过（不得因本次改动破坏） | P0 |

---

## 9. 内嵌已知坑（来自项目记忆）

| 坑 | 根因 | 修法 |
|---|---|---|
| `.bat` 双击闪退 | 文件被写成 LF 换行 | **改完 `.bat` 必须转 CRLF**（保留无 BOM） |
| 二进制被写坏 | 有进程把二进制当文本往返处理 | 二进制资源必须入版本控制；改完用 `git cat-file -s` 核对大小 |
| 历史缩略图失效 | `uploads/` 有 24h 惰性回收 | 缩略图**存 DB BLOB**，不存文件 |
| 服务假死 | `async def` 内同步阻塞 | 新端点一律用 `def`（FastAPI 自动走线程池） |
| 前端硬编码阈值 | 曾把 OOD 阈值写死在前端 | 阈值与作物清单一律从 `/api/v1/meta` 取 |
| 处方来源不透明 | 曾静默回落模板 | 响应体必须带 `prescription_source` |

---

## 10. 边界与约束

- **离线优先**：SQLite 本地文件；语音用浏览器内置。**除大模型处方外，全链路离线可用。**
- 单用户数据量假设：< 1000 条历史；列表分页默认 20 条。
- 密码长度 8–64；用户名 3–20，仅字母数字下划线。
- 历史记录保留策略：**不自动清理**（用户可手动删）。
- 缩略图统一最长边 ≤320px、JPEG 质量 80，单条记录约 20–40KB。

---

## 11. 端到端验证步骤（锁定）

```bash
# 1. 回归（不得破坏既有功能）
.venv\Scripts\python.exe -m pytest tests -v          # 期望 14 passed

# 2. 启动
run.bat

# 3. 认证链路
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"demo","password":"demo1234"}'
# 断言：200 + 返回 token

# 4. 病例库
curl http://127.0.0.1:8000/api/v1/cases
# 断言：14 个作物、合计 38 个类别

# 5. 未授权访问必须 401
curl -i http://127.0.0.1:8000/api/v1/history
# 断言：401

# 6. 带 token 诊断 → 自动入库
curl -X POST http://127.0.0.1:8000/api/v1/predict \
     -H "Authorization: Bearer <token>" \
     -F "file=@test_assets/supported_diseased/Tomato__Early_blight.jpg"
# 断言：200 + history_id 非空

# 7. 历史可查到
curl -H "Authorization: Bearer <token>" "http://127.0.0.1:8000/api/v1/history?limit=5"
# 断言：total >= 1
```

---

## 12. 变更记录

| 日期 | 变更 | 原因 | 影响范围 |
|------|------|------|----------|
| 2026-09-21 | 首次锁定 | 用户提出前端功能扩展需求并确认四项选型 | 全量 |
