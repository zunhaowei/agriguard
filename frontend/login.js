/**
 * 禾目 AgriGuard · 登录 / 注册页交互  agri-guard/v1.0-ext
 * 原创作品 · 2026-09-21 · 禾目团队独立实现
 *
 * 契约：Spec §5 /auth/*，Spec §8 AC-01 ~ AC-04。
 * 错误文案取自设计规格 §4 文案总表：凭据错误**不区分**用户名不存在与密码错误
 * （AC-04，避免账号存在性泄露）。
 */
(function () {
  "use strict";

  var AGRI = window.AGRI;
  if (!AGRI) return;

  var USERNAME_RE = /^[A-Za-z0-9_]{3,20}$/;
  var PASSWORD_MIN = 8;
  var PASSWORD_MAX = 64;

  var MSG = {
    usernameRequired: "请先填写用户名。",
    usernameFormat: "用户名需 3–20 位，只能用字母、数字或下划线",
    passwordRequired: "请先填写密码。",
    passwordLength: "密码至少 8 位",
    credentials: "用户名或密码错误，请再试一次",
    usernameTaken: "这个用户名已经有人用了，换一个试试",
    fallback: "操作失败，请稍后再试"
  };

  // ---------------------------------------------------------------------------
  // 元素
  // ---------------------------------------------------------------------------
  var tabs = [document.getElementById("tab-login"), document.getElementById("tab-register")];
  var panels = [document.getElementById("panel-login"), document.getElementById("panel-register")];
  var noticeSlot = document.getElementById("notice-slot");
  var fillDemoBtn = document.getElementById("fill-demo");

  var loginForm = document.getElementById("form-login");
  var loginAlert = document.getElementById("login-alert");
  var loginUser = document.getElementById("login-username");
  var loginPw = document.getElementById("login-password");
  var loginUserErr = document.getElementById("login-username-err");
  var loginPwErr = document.getElementById("login-password-err");
  var loginSubmit = document.getElementById("login-submit");

  var regForm = document.getElementById("form-register");
  var regAlert = document.getElementById("register-alert");
  var regUser = document.getElementById("register-username");
  var regDisplay = document.getElementById("register-display");
  var regPw = document.getElementById("register-password");
  var regUserErr = document.getElementById("register-username-err");
  var regPwErr = document.getElementById("register-password-err");
  var regSubmit = document.getElementById("register-submit");

  // ---------------------------------------------------------------------------
  // 小工具
  // ---------------------------------------------------------------------------
  function setAlert(container, kind, message) {
    AGRI.clear(container);
    if (!message) return null;
    var box = AGRI.el("div", "alert alert-" + kind);
    box.setAttribute("role", kind === "error" ? "alert" : "status");
    box.innerHTML = AGRI.iconSvg(kind === "error" ? "alert" : kind === "success" ? "check" : "info", 20);
    box.appendChild(AGRI.el("span", null, message));
    container.appendChild(box);
    return box;
  }

  function setFieldError(input, holder, message) {
    AGRI.clear(holder);
    if (message) {
      holder.hidden = false;
      holder.innerHTML = AGRI.iconSvg("alert", 16);
      holder.appendChild(AGRI.el("span", null, message));
      input.setAttribute("aria-invalid", "true");
    } else {
      holder.hidden = true;
      input.setAttribute("aria-invalid", "false");
    }
  }

  function setFormEnabled(form, enabled) {
    var nodes = form.querySelectorAll("input");
    for (var i = 0; i < nodes.length; i++) nodes[i].disabled = !enabled;
  }

  /** 只接受同目录下的 .html 文件名，避免 ?next= 变成开放重定向。 */
  function safeNext() {
    var raw = "";
    try {
      raw = new URLSearchParams(location.search).get("next") || "";
    } catch (e) {
      raw = "";
    }
    return /^[A-Za-z0-9_-]+\.html$/.test(raw) ? raw : "";
  }

  function enterTarget() {
    var next = safeNext();
    return next ? "/static/" + next : "/static/index.html";
  }

  // ---------------------------------------------------------------------------
  // 分段切换
  // ---------------------------------------------------------------------------
  var activeIndex = 0;

  function selectTab(index, focusTab) {
    activeIndex = index;
    for (var i = 0; i < tabs.length; i++) {
      var on = i === index;
      tabs[i].setAttribute("aria-selected", on ? "true" : "false");
      tabs[i].tabIndex = on ? 0 : -1;
      panels[i].hidden = !on;
    }
    if (focusTab) tabs[index].focus();
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener("click", function () {
      selectTab(index, false);
    });
    tab.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft" || e.key === "Home" || e.key === "End") {
        e.preventDefault();
        var target =
          e.key === "ArrowRight" ? (index + 1) % tabs.length
          : e.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length
          : e.key === "Home" ? 0
          : tabs.length - 1;
        selectTab(target, true);
      }
    });
  });

  // ---------------------------------------------------------------------------
  // 演示账号一键填入
  // ---------------------------------------------------------------------------
  fillDemoBtn.addEventListener("click", function () {
    selectTab(0, false);
    loginUser.value = "demo";
    loginPw.value = "demo1234";
    setFieldError(loginUser, loginUserErr, "");
    setFieldError(loginPw, loginPwErr, "");
    setAlert(loginAlert, null, "");
    loginSubmit.focus();
  });

  // ---------------------------------------------------------------------------
  // 提交
  // ---------------------------------------------------------------------------
  function onAuthSuccess(data, slot, otherSlot, successText) {
    if (!data || !data.token) {
      setAlert(slot, "error", MSG.fallback);
      return;
    }
    AGRI.setSession(data.token, data.user);
    setAlert(otherSlot, null, "");
    setAlert(slot, "success", successText);
    setTimeout(function () {
      location.replace(enterTarget());
    }, 350);
  }

  function handleFailure(err, alertSlot, opts) {
    var status = err && err.status;
    var message;
    if (status === 401 || status === 409 || status === 400) {
      message = opts.byStatus[status] || (err && err.message) || MSG.fallback;
    } else {
      // 网络不可达（status 0）由请求层给出「暂时连不上服务…」，直接用原文
      message = (err && err.message) || MSG.fallback;
    }
    setAlert(alertSlot, "error", message);
  }

  loginForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var username = loginUser.value.trim();
    var password = loginPw.value;

    setAlert(loginAlert, null, "");
    setFieldError(loginUser, loginUserErr, username ? "" : MSG.usernameRequired);
    setFieldError(loginPw, loginPwErr, password ? "" : MSG.passwordRequired);
    if (!username || !password) return;

    AGRI.setBusy(loginSubmit, true, "正在登录…");
    setFormEnabled(loginForm, false);

    AGRI.apiJson("/api/v1/auth/login", {
      method: "POST",
      body: { username: username, password: password }
    })
      .then(function (data) {
        onAuthSuccess(data, loginAlert, regAlert, "登录成功，正在进入…");
      })
      .catch(function (err) {
        handleFailure(err, loginAlert, { byStatus: { 401: MSG.credentials } });
      })
      .finally(function () {
        if (!AGRI.currentUser()) {
          AGRI.setBusy(loginSubmit, false);
          setFormEnabled(loginForm, true);
        }
      });
  });

  regForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var username = regUser.value.trim();
    var displayName = regDisplay.value.trim();
    var password = regPw.value;

    setAlert(regAlert, null, "");

    var usernameError = "";
    if (!username) usernameError = MSG.usernameRequired;
    else if (!USERNAME_RE.test(username)) usernameError = MSG.usernameFormat;
    var passwordError = "";
    if (!password) passwordError = MSG.passwordRequired;
    else if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
      passwordError = MSG.passwordLength;
    }

    setFieldError(regUser, regUserErr, usernameError);
    setFieldError(regPw, regPwErr, passwordError);
    if (usernameError || passwordError) return;

    AGRI.setBusy(regSubmit, true, "正在创建…");
    setFormEnabled(regForm, false);

    var body = { username: username, password: password };
    if (displayName) body.display_name = displayName;

    AGRI.apiJson("/api/v1/auth/register", { method: "POST", body: body })
      .then(function (data) {
        onAuthSuccess(data, regAlert, loginAlert, "账号创建好了，正在进入…");
      })
      .catch(function (err) {
        var status = err && err.status;
        if (status === 409) {
          setFieldError(regUser, regUserErr, MSG.usernameTaken);
          setAlert(regAlert, "error", MSG.usernameTaken);
        } else if (status === 400) {
          // 客户端已先校验；走到这里说明是格式之外的服务端规则，落到表单级提示
          handleFailure(err, regAlert, { byStatus: {} });
        } else {
          handleFailure(err, regAlert, { byStatus: {} });
        }
      })
      .finally(function () {
        if (!AGRI.currentUser()) {
          AGRI.setBusy(regSubmit, false);
          setFormEnabled(regForm, true);
        }
      });
  });

  // ---------------------------------------------------------------------------
  // 启动
  // ---------------------------------------------------------------------------
  selectTab(0, false);

  AGRI.state.ready.then(function (user) {
    if (!user) {
      loginUser.focus(); // 默认停在「登录」分段，用户名自动聚焦
      return;
    }
    // 已登录时不弹走用户（便于随时回来看看这一页），只给一条可继续的提示
    var name = user.display_name || user.username;
    var box = setAlert(noticeSlot, "info", "你已经登录为「" + name + "」，可以直接去诊断或查看记录。");
    if (box) box.appendChild(AGRI.link("btn btn-secondary", "/static/index.html", "camera", "去诊断", 20));
  });
})();
