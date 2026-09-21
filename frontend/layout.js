/**
 * 禾目 AgriGuard · 全站共享脚本 agri-guard/v1.0-ext
 * 原创作品 · 2026-09-21 · 禾目团队独立实现
 *
 * 【职责】（Spec §6「导航」+ 设计规格 §3.1）
 *   1. 注入全站统一的顶部导航 `.site-nav` 与移动端底部标签栏 `.tabbar`
 *      —— 取代 index.html 里原先的裸 `.topbar`，消除「同一页面两条导航」。
 *   2. 登录态：启动时以 /api/v1/auth/me 校验令牌，未登录/已登录两态切换 + 登出。
 *   3. 受保护页守卫：未登录跳登录页（带 next 回跳）；**先判定再渲染**，
 *      避免先闪一屏空列表再跳走。
 *   4. 共享工具：描边 SVG 图标表、请求封装（统一 Authorization 与 401 收敛）、
 *      轻提示、弹层（含 focus trap / ESC / 焦点归还）、空状态、骨架屏。
 *
 * 【纪律】
 * - 图标一律描边 SVG：fill="none" / stroke="currentColor" / stroke-width="2" /
 *   圆角端点，尺寸仅 16 / 20 / 24px。全项目禁止 emoji 作功能图标。
 * - 不硬编码颜色，一律引用 styles.css 的 CSS 变量。
 * - 与既有 app.js 同一写法：var + function + 原生 DOM API；零构建、零框架、零依赖。
 */
(function () {
  "use strict";

  var TOKEN_KEY = "agri_token";
  var LOGIN_URL = "/static/login.html";
  var HOME_URL = "/static/index.html";
  var CASES_URL = "/static/cases.html";
  var HISTORY_URL = "/static/history.html";
  var VERSION = "v1.0-ext";

  // ---------------------------------------------------------------------------
  // 图标表（统一描边风格，尺寸仅 16 / 20 / 24 三档；禁止 emoji）
  // 前 9 个自 app.js 原样迁入，保证既有渲染结果逐像素一致。
  // ---------------------------------------------------------------------------
  var ICON_PATHS = {
    chevron: '<path d="m6 9 6 6 6-6"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    alert:
      '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    shield:
      '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    flask:
      '<path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/><path d="M6.453 15h11.094"/><path d="M8.5 2h7"/>',
    calendar:
      '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>',
    activity:
      '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    rotate:
      '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    imageOff:
      '<line x1="2" x2="22" y1="2" y2="22"/><path d="M10.41 10.41a2 2 0 1 1-2.83-2.83"/><line x1="13.5" x2="6" y1="13.5" y2="21"/><path d="M18 12l3 3"/><path d="M3 3l18 18"/>',
    // —— 本次新增（设计规格 §1.5 锁定清单）——
    volume:
      '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    volumeOff:
      '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    arrowLeft: '<path d="m15 18-6-6 6-6"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    trash:
      '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    user: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    logIn:
      '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" x2="3" y1="12" y2="12"/>',
    logOut:
      '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    bookOpen:
      '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    camera:
      '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
    check: '<path d="M20 6 9 17l-5-5"/>'
  };

  function iconSvg(name, size) {
    return (
      '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true">' + (ICON_PATHS[name] || "") + "</svg>"
    );
  }

  // ---------------------------------------------------------------------------
  // DOM 小工具
  // ---------------------------------------------------------------------------
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(className, iconName, label, size) {
    var b = el("button", className);
    b.type = "button";
    b.innerHTML = iconSvg(iconName || "info", size || 20);
    if (label) b.appendChild(document.createTextNode(label));
    return b;
  }

  function link(className, href, iconName, label, size) {
    var a = el("a", className);
    a.href = href;
    a.innerHTML = iconSvg(iconName || "info", size || 20);
    if (label) a.appendChild(document.createTextNode(label));
    return a;
  }

  function clear(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }

  function pct(v) {
    var n = Number(v);
    return isFinite(n) ? (n * 100).toFixed(1) + "%" : "—";
  }

  function num(v, digits) {
    var n = Number(v);
    return isFinite(n) ? n.toFixed(digits === undefined ? 2 : digits) : "—";
  }

  function fmtDateTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    function pad(n) {
      return n < 10 ? "0" + n : String(n);
    }
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes())
    );
  }

  function setBusy(btn, busy, busyText) {
    if (!btn) return;
    if (busy) {
      if (!btn.getAttribute("data-idle-html")) {
        btn.setAttribute("data-idle-html", btn.innerHTML);
      }
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      btn.innerHTML = '<span class="spinner" aria-hidden="true"></span>';
      btn.appendChild(document.createTextNode(busyText || "正在处理…"));
    } else {
      var html = btn.getAttribute("data-idle-html");
      if (html !== null) btn.innerHTML = html;
      btn.removeAttribute("data-idle-html");
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
    }
  }

  // ---------------------------------------------------------------------------
  // 登录态与令牌
  // ---------------------------------------------------------------------------
  function readToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || "";
    } catch (e) {
      return "";
    }
  }

  function writeToken(token) {
    state.token = token || "";
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (e) {
      /* 隐私模式等场景下 localStorage 不可用：本次会话内仍以前端内存态为准 */
    }
  }

  var state = {
    token: readToken(),
    user: null,
    userResolved: false,
    guard: false,
    guardNext: "history.html",
    ready: null
  };
  state.userResolved = !state.token;

  function currentFile() {
    var p = location.pathname || "";
    var i = p.lastIndexOf("/");
    return p.slice(i + 1) || "index.html";
  }

  function pageKey() {
    var b = document.body;
    return (b && b.getAttribute("data-page")) || "";
  }

  function redirectToLogin(next) {
    if (currentFile() === "login.html") return;
    var target = next || currentFile();
    location.replace(LOGIN_URL + "?next=" + encodeURIComponent(target));
  }

  // ---------------------------------------------------------------------------
  // 请求封装：统一带 Authorization；统一把 401 收敛为「清令牌 + 可选跳登录」
  // ---------------------------------------------------------------------------
  function ApiError(message, status) {
    this.name = "ApiError";
    this.message = message;
    this.status = status || 0;
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  function authHeaders(extra) {
    var h = {};
    var k;
    if (extra) {
      for (k in extra) {
        if (Object.prototype.hasOwnProperty.call(extra, k)) h[k] = extra[k];
      }
    }
    if (state.token) h.Authorization = "Bearer " + state.token;
    return h;
  }

  function apiJson(path, opts) {
    opts = opts || {};
    var init = { method: opts.method || "GET", headers: authHeaders(opts.headers) };
    if (opts.body !== undefined && opts.body !== null) {
      if (typeof FormData !== "undefined" && opts.body instanceof FormData) {
        init.body = opts.body; // FormData 由浏览器自行设置 multipart 边界
      } else {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(opts.body);
      }
    }
    if (opts.signal) init.signal = opts.signal;

    return fetch(path, init).then(
      function (res) {
        if (res.status === 401) {
          writeToken("");
          state.user = null;
          state.userResolved = true;
          renderNav();
          if (opts.auth === "required") redirectToLogin(state.guardNext);
          throw new ApiError("登录状态已过期，请重新登录。", 401);
        }
        return res.text().then(function (txt) {
          var data = null;
          if (txt) {
            try {
              data = JSON.parse(txt);
            } catch (e) {
              data = null;
            }
          }
          if (!res.ok) {
            var msg = data && (data.reason || data.detail);
            if (typeof msg !== "string" || !msg) msg = "服务返回 " + res.status + "，请稍后重试。";
            throw new ApiError(msg, res.status);
          }
          if (data === null) throw new ApiError("服务返回的内容无法解析，请稍后重试。", res.status);
          return data;
        });
      },
      function (err) {
        if (err instanceof ApiError) throw err;
        throw new ApiError("暂时连不上服务，请确认服务已启动后再试。", 0);
      }
    );
  }

  // ---------------------------------------------------------------------------
  // 轻提示
  // ---------------------------------------------------------------------------
  var toastRegion = null;

  function ensureToastRegion() {
    if (toastRegion && toastRegion.parentNode) return toastRegion;
    toastRegion = el("div", "toast-region");
    toastRegion.setAttribute("role", "status");
    toastRegion.setAttribute("aria-live", "polite");
    document.body.appendChild(toastRegion);
    return toastRegion;
  }

  function toast(message, kind) {
    if (!document.body) {
      document.addEventListener("DOMContentLoaded", function () {
        toast(message, kind);
      });
      return null;
    }
    var region = ensureToastRegion();
    var k = kind || "info";
    var item = el("div", "toast toast-" + k);
    if (k === "error") item.setAttribute("role", "alert");
    item.innerHTML = iconSvg(k === "success" ? "check" : k === "error" ? "alert" : "info", 20);
    item.appendChild(el("span", "toast-msg", message));
    region.appendChild(item);
    setTimeout(function () {
      if (item.parentNode) item.parentNode.removeChild(item);
    }, k === "error" ? 5000 : 3000);
    return item;
  }

  // ---------------------------------------------------------------------------
  // 空状态
  // ---------------------------------------------------------------------------
  function empty(opts) {
    opts = opts || {};
    var box = el("div", "empty");
    box.innerHTML = iconSvg(opts.icon || "info", 24);
    if (box.firstChild) box.firstChild.setAttribute("class", "empty-icon");
    if (opts.title) box.appendChild(el("p", "empty-title", opts.title));
    if (opts.text) box.appendChild(el("p", "empty-text", opts.text));
    if (opts.actionLabel && opts.onAction) {
      var kind = opts.actionKind || "primary";
      var b = button("btn btn-" + kind, opts.actionIcon || null, opts.actionLabel, 20);
      b.addEventListener("click", opts.onAction);
      box.appendChild(b);
    }
    return box;
  }

  // ---------------------------------------------------------------------------
  // 语义 pill（与 app.js 原实现逐字一致，避免两套阈值）
  // ---------------------------------------------------------------------------
  function confidencePill(conf) {
    var n = Number(conf);
    if (!isFinite(n)) return el("span", "pill pill-neutral", "可信度 —");
    var level = n >= 0.85 ? "高" : n >= 0.6 ? "中" : "低";
    var cls = n >= 0.85 ? "pill-success" : n >= 0.6 ? "pill-warn" : "pill-danger";
    var pill = el("span", "pill " + cls);
    pill.appendChild(el("span", null, "可信度 " + level));
    pill.appendChild(el("span", "pill-num", pct(n)));
    return pill;
  }

  function severityPill(grade) {
    var text = grade || "待评估";
    var cls = "pill-neutral";
    if (text === "健康") cls = "pill-success";
    else if (text === "轻") cls = "pill-warn";
    else if (text === "中" || text === "重") cls = "pill-danger";
    var pill = el("span", "pill " + cls);
    pill.innerHTML = iconSvg("activity", 16);
    pill.appendChild(el("span", null, "严重程度 " + text));
    return pill;
  }

  // ---------------------------------------------------------------------------
  // 处方区块（与 app.js 原实现同构，历史详情弹层复用）
  // ---------------------------------------------------------------------------
  var RX_BLOCKS = [
    { key: "biological", label: "生物防治", icon: "shield" },
    { key: "chemical", label: "化学用药", icon: "flask" },
    { key: "tips", label: "日常管理", icon: "calendar" }
  ];

  function renderPrescription(rx, container) {
    clear(container);
    if (!rx) {
      container.appendChild(
        el("p", "empty-note", "未识别到有效病害，请重拍或换一张清晰照片。")
      );
      return;
    }
    RX_BLOCKS.forEach(function (cfg) {
      var text = rx[cfg.key];
      if (text === undefined || text === null || text === "") return;
      var block = el("div", "rx-block");
      var head = el("div", "rx-head");
      head.innerHTML = iconSvg(cfg.icon, 20);
      head.appendChild(el("span", null, cfg.label));
      block.appendChild(head);
      block.appendChild(el("p", null, String(text)));
      container.appendChild(block);
    });
    if (!container.childNodes.length) {
      container.appendChild(el("p", "empty-note", "本次未返回处方内容。"));
    }
  }

  // ---------------------------------------------------------------------------
  // 弹层（详情 / 确认）：role=dialog + aria-modal + focus trap + ESC + 焦点归还
  // ---------------------------------------------------------------------------
  var dlgSeq = 0;

  function openDialog(opts) {
    opts = opts || {};
    var lastFocus = document.activeElement;
    var backdrop = el("div", "dialog-backdrop");
    var dlg = el("div", "dialog");
    var titleId = "dialog-title-" + ++dlgSeq;
    dlg.setAttribute("role", "dialog");
    dlg.setAttribute("aria-modal", "true");
    dlg.setAttribute("aria-labelledby", titleId);

    var head = el("div", "dialog-head");
    var headText = el("div");
    var h2 = el("h2", "dialog-title", opts.title || "详情");
    h2.id = titleId;
    headText.appendChild(h2);
    if (opts.sub) headText.appendChild(el("p", "dialog-sub", opts.sub));
    var closeBtn = button("btn btn-icon", "x", null, 20);
    closeBtn.setAttribute("aria-label", opts.closeLabel || "关闭对话框");
    head.appendChild(headText);
    head.appendChild(closeBtn);

    var body = el("div", "dialog-body");
    if (opts.buildBody) opts.buildBody(body);

    dlg.appendChild(head);
    dlg.appendChild(body);

    if (opts.buildFoot) {
      var foot = el("div", "dialog-foot");
      opts.buildFoot(foot, function () {
        close();
      });
      dlg.appendChild(foot);
    }

    backdrop.appendChild(dlg);

    function focusables() {
      var nodes = dlg.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),' +
          ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      return Array.prototype.slice.call(nodes);
    }

    function onKey(e) {
      if (e.key === "Escape" || e.key === "Esc") {
        e.preventDefault();
        close();
        return;
      }
      if (e.key === "Tab") {
        var list = focusables();
        if (!list.length) return;
        var first = list[0];
        var last = list[list.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      document.removeEventListener("keydown", onKey, true);
      if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
      if (lastFocus && typeof lastFocus.focus === "function") {
        try {
          lastFocus.focus();
        } catch (e) {
          /* 触发元素可能已被移除 */
        }
      }
      if (opts.onClose) opts.onClose();
    }

    closeBtn.addEventListener("click", close);
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop && opts.dismissible !== false) close();
    });

    document.body.appendChild(backdrop);
    document.addEventListener("keydown", onKey, true);
    closeBtn.focus();

    return { close: close, root: dlg, body: body };
  }

  // ---------------------------------------------------------------------------
  // 顶部导航 + 底部标签栏
  // ---------------------------------------------------------------------------
  var NAV_ITEMS = [
    { key: "index", href: HOME_URL, icon: "camera", label: "诊断" },
    { key: "cases", href: CASES_URL, icon: "bookOpen", label: "病例库" },
    { key: "history", href: HISTORY_URL, icon: "clock", label: "历史记录" }
  ];

  var navAuthEl = null;
  var tabbarMineEl = null;

  function avatarChar(user) {
    var s = (user && (user.display_name || user.username)) || "用";
    s = String(s).trim();
    return s.charAt(0) || "用";
  }

  function buildHeader() {
    var key = pageKey();
    var header = el("header", "site-nav");
    var inner = el("div", "site-nav-inner");

    var brand = el("a", "brand");
    brand.href = HOME_URL;
    var mark = el("img", "brand-mark");
    mark.src = "/static/logo_icon.svg";
    mark.alt = "";
    mark.width = 32;
    mark.height = 32;
    brand.appendChild(mark);
    var brandName = el("span", "brand-name");
    brandName.appendChild(document.createTextNode("禾目"));
    brandName.appendChild(el("span", "brand-latin", "AgriGuard"));
    brand.appendChild(brandName);

    // 合规标识：沿用既有 .badge-compliance（<768px 隐藏），
    // 与页脚「本作品使用 AI 辅助开发」互为呼应。
    var badge = el("span", "badge-compliance", "AI 辅助制作");

    var nav = el("nav", "nav-links");
    nav.setAttribute("aria-label", "主导航");
    NAV_ITEMS.forEach(function (item) {
      var a = link("nav-link", item.href, item.icon, item.label, 16);
      if (item.key === key) a.setAttribute("aria-current", "page");
      nav.appendChild(a);
    });

    var auth = el("div", "nav-auth");

    inner.appendChild(brand);
    inner.appendChild(badge);
    inner.appendChild(nav);
    inner.appendChild(auth);
    header.appendChild(inner);
    navAuthEl = auth;
    return header;
  }

  function buildTabbar() {
    var key = pageKey();
    var bar = el("nav", "tabbar");
    bar.setAttribute("aria-label", "快捷导航");
    NAV_ITEMS.forEach(function (item) {
      var a = link("tabbar-item", item.href, item.icon, item.label, 20);
      if (item.key === key) a.setAttribute("aria-current", "page");
      bar.appendChild(a);
    });
    var mine = link("tabbar-item", LOGIN_URL, "user", "我的", 20);
    mine.setAttribute("data-mine", "1");
    bar.appendChild(mine);
    tabbarMineEl = mine;
    return bar;
  }

  function fillAuth(container) {
    clear(container);
    var user = state.user;

    if (!state.userResolved) return; // 校验未回来前留空，避免「登录 → 用户名」闪跳

    if (user) {
      var chip = el("span", "user-chip");
      var av = el("span", "user-avatar", avatarChar(user));
      av.setAttribute("aria-hidden", "true");
      chip.appendChild(av);
      chip.appendChild(el("span", "user-name", user.display_name || user.username || "用户"));
      if (user.is_demo) chip.appendChild(el("span", "badge-demo", "演示"));
      container.appendChild(chip);

      var out = button("btn btn-ghost", "logOut", "退出", 20);
      out.setAttribute("aria-label", "退出登录");
      out.addEventListener("click", function () {
        logout();
      });
      container.appendChild(out);
      return;
    }

    if (pageKey() === "login") {
      // 登录页的认证区不再放「登录」（会自我循环），改为返回诊断入口
      var back = link("btn btn-ghost", HOME_URL, "camera", "返回诊断", 20);
      container.appendChild(back);
      return;
    }

    container.appendChild(link("btn btn-primary", LOGIN_URL, "logIn", "登录", 20));
  }

  function renderNav() {
    if (navAuthEl) fillAuth(navAuthEl);
    if (tabbarMineEl) {
      // 未登录 → 指向登录页（设计规格 §3.1）；已登录 → 指向「我的诊断记录」
      tabbarMineEl.href = state.user ? HISTORY_URL : LOGIN_URL;
    }
  }

  function fetchMe() {
    if (!state.token) {
      state.user = null;
      state.userResolved = true;
      return Promise.resolve(null);
    }
    return apiJson("/api/v1/auth/me").then(
      function (data) {
        state.user = data && data.user ? data.user : null;
        state.userResolved = true;
        return state.user;
      },
      function () {
        // 令牌无效 / 服务不可达：一律按未登录呈现，不报错、不弹窗（设计规格 §3.1 降级态）
        state.user = null;
        state.userResolved = true;
        return null;
      }
    );
  }

  function logout() {
    var req;
    if (state.token) {
      req = apiJson("/api/v1/auth/logout", { method: "POST" }).catch(function () {
        return null; // 服务端失败也必须把本地登录态清掉，否则用户会卡在假登录态
      });
    } else {
      req = Promise.resolve(null);
    }
    return req.then(function () {
      writeToken("");
      state.user = null;
      state.userResolved = true;
      renderNav();
      if (state.guard) {
        redirectToLogin(state.guardNext);
        return;
      }
      toast("已退出登录", "success");
    });
  }

  /**
   * 受保护页守卫：先判定登录态，再决定是否渲染。
   * @returns Promise<user|null> —— 返回 null 表示已触发跳转，调用方必须停止渲染。
   */
  function guard(nextFile) {
    state.guard = true;
    state.guardNext = nextFile || currentFile();
    return state.ready.then(function (user) {
      if (!user) {
        redirectToLogin(state.guardNext);
        return null;
      }
      return user;
    });
  }

  function boot() {
    var header = buildHeader();
    document.body.insertBefore(header, document.body.firstChild);
    document.body.appendChild(buildTabbar());
    renderNav();
  }

  // ---------------------------------------------------------------------------
  // 对外命名空间
  // ---------------------------------------------------------------------------
  window.AGRI = {
    VERSION: VERSION,
    ICON_PATHS: ICON_PATHS,
    iconSvg: iconSvg,
    el: el,
    button: button,
    link: link,
    clear: clear,
    pct: pct,
    num: num,
    fmtDateTime: fmtDateTime,
    setBusy: setBusy,
    toast: toast,
    empty: empty,
    openDialog: openDialog,
    confidencePill: confidencePill,
    severityPill: severityPill,
    renderPrescription: renderPrescription,
    apiJson: apiJson,
    /** 登录/注册成功后写入会话（令牌 + 用户），并刷新导航认证区 */
    setSession: function (token, user) {
      writeToken(token || "");
      state.user = user || null;
      state.userResolved = true;
      renderNav();
    },
    getToken: function () {
      return state.token;
    },
    currentUser: function () {
      return state.user;
    },
    state: state,
    guard: guard,
    logout: logout,
    redirectToLogin: redirectToLogin,
    currentFile: currentFile,
    loginUrl: function (next) {
      return LOGIN_URL + (next ? "?next=" + encodeURIComponent(next) : "");
    },
    urls: { home: HOME_URL, login: LOGIN_URL, cases: CASES_URL, history: HISTORY_URL }
  };

  // 启动：/auth/me 与页面解析并行发起，谁先到都不影响
  state.ready = fetchMe().then(function (user) {
    renderNav();
    return user;
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
