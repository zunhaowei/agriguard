/**
 * 禾目 AgriGuard 前端交互核心 agri-guard/v1.0
 * 原创作品 · 2026-09-20 · 禾目团队独立实现
 *
 * 【本次审查修正】
 * 1. 阈值与作物清单改为从后端 /api/v1/meta 与每次响应读取 —— 原先前端各存一份
 *    硬编码副本，与后端无同步机制，历史上阈值改过两次，随时可能漂移成
 *    "界面写的数"与"后端判的数"不一致。
 * 2. 消除对象 URL 内存泄漏（原先 createObjectURL 从不 revoke）。
 * 3. 补齐加载态 / 并发守卫 / 超时 / 重试 —— 原先只有一行纯文本状态，
 *    连点两次会产生两个并发请求，且陈旧响应可能覆盖新结果。
 * 4. 所有硬编码色值收敛为语义 class，颜色统一由 CSS token 管理。
 * 5. 全部动态文本走 textContent / createElement，杜绝字符串拼 HTML 的转义风险。
 */
(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // 共享层：图标表 / 请求封装 / 轻提示 / pill / 处方区块都由 layout.js 提供，
  // 全站唯一一份实现。本文件不再各存一份副本 —— 历史上"两套阈值各写一遍"
  // 就是这么漂移的（见文件头的第 1 条审查修正）。
  // ---------------------------------------------------------------------------
  var AGRI = window.AGRI;
  if (!AGRI) {
    // 加载顺序被破坏时必须给出可见提示，而不是渲染出半个页面
    document.addEventListener("DOMContentLoaded", function () {
      var box = document.createElement("p");
      box.className = "status status-error";
      box.textContent = "界面脚本加载不完整（缺少 layout.js），请刷新页面重试。";
      var host = document.querySelector(".app") || document.body;
      host.insertBefore(box, host.firstChild);
    });
    return;
  }

  var CFG = {
    work: "AGRI-GUARD",
    ver: "v1.0",
    ts: "2026-09-20",
    signature: "HM-AG-2026-0920",
    requestTimeoutMs: 30000
  };

  // ---------------------------------------------------------------------------
  // 元素句柄
  // ---------------------------------------------------------------------------
  var dropzone = document.getElementById("dropzone");
  var fileInput = document.getElementById("file");
  var demoBtn = document.getElementById("demo-btn");
  var oodBtn = document.getElementById("ood-btn");
  var demoThumb = document.getElementById("demo-thumb");
  var dropzoneHint = document.getElementById("dropzone-hint");
  var previewWrap = document.getElementById("preview-wrap");
  var preview = document.getElementById("preview");
  var statusEl = document.getElementById("status");
  var resultEl = document.getElementById("result");
  var verdictEl = document.getElementById("verdict");
  var heatmapBlock = document.getElementById("heatmap-block");
  var heatmapImg = document.getElementById("heatmap-img");
  var detailBlock = document.getElementById("detail-block");
  var prescriptionEl = document.getElementById("prescription");
  var cropsList = document.getElementById("crops-list");
  var cropsCount = document.getElementById("crops-count");
  var ttsRow = document.getElementById("tts-row");
  var ttsBtn = document.getElementById("tts-btn");
  var ttsIcon = document.getElementById("tts-icon");
  var ttsLabel = document.getElementById("tts-label");

  // ---------------------------------------------------------------------------
  // 图标：统一描边风格，尺寸仅 16 / 20 / 24 三档；不使用任何 emoji。
  // 表与渲染函数均在 layout.js（全站唯一）。
  // ---------------------------------------------------------------------------
  var ICON_PATHS = AGRI.ICON_PATHS;
  var iconSvg = AGRI.iconSvg;

  // ---------------------------------------------------------------------------
  // 小工具（与 layout.js 同源，此处仅取别名，避免同名不同实现）
  // ---------------------------------------------------------------------------
  var el = AGRI.el;
  var pct = AGRI.pct;
  var num = AGRI.num;

  // ---------------------------------------------------------------------------
  // 业务常量真值：从后端下发，前端不硬编码
  // ---------------------------------------------------------------------------
  var meta = {
    oodRejectThreshold: null,
    oodWarnThreshold: null,
    maxUploadMB: null,
    crops: []
  };

  // 兜底常量仅在 /api/v1/meta 不可达时使用（后端是唯一真源）。
  // 注意这里只用于"显示降级"，不参与任何判断逻辑。
  var FALLBACK = { reject: null, warn: null, maxUploadMB: null };

  function applyMeta(data) {
    if (!data || typeof data !== "object") return;
    meta.oodRejectThreshold = data.ood_reject_threshold != null ? Number(data.ood_reject_threshold) : null;
    meta.oodWarnThreshold = data.ood_warn_threshold != null ? Number(data.ood_warn_threshold) : null;
    meta.maxUploadMB = data.max_upload_mb != null ? Number(data.max_upload_mb) : null;
    meta.crops = Array.isArray(data.supported_crops) ? data.supported_crops : [];

    if (meta.crops.length) {
      cropsList.textContent = meta.crops.join("、");
      cropsCount.textContent = "（" + meta.crops.length + " 种）";
    } else {
      cropsList.textContent =
        "后端未返回作物清单。请确认服务运行正常后刷新页面。";
      cropsCount.textContent = "";
    }

    if (meta.maxUploadMB) {
      dropzoneHint.textContent =
        "支持 JPG / PNG / WEBP / BMP，单张不超过 " + meta.maxUploadMB + "MB";
    }
  }

  function loadMeta() {
    fetch("/api/v1/meta")
      .then(function (r) {
        if (!r.ok) throw new Error("meta " + r.status);
        return r.json();
      })
      .then(applyMeta)
      .catch(function () {
        cropsList.textContent = "无法读取后端配置，请确认服务已启动。";
        cropsCount.textContent = "";
      });
  }

  // ---------------------------------------------------------------------------
  // 原创指纹自证（供抄袭取证与原创性举证）
  // ---------------------------------------------------------------------------
  function agriOriginClaim() {
    var s = "color:#2e7d4f;font-weight:600;";
    var g = "color:#64748b;";
    try {
      console.log("%c禾目 AgriGuard · 作物病虫害智能诊断系统", s);
      console.log("%c原创作品 " + CFG.work + "/" + CFG.ver + " · " + CFG.ts + " · 禾目团队独立设计与实现", s);
      console.log("%c署名标识 " + CFG.signature + " · 未经许可请勿盗用", g);
      console.log("%c输入 __agri_guard__.verify() 可校验本页原创指纹完整性", g);
    } catch (e) {
      /* 控制台不可用时静默 */
    }
  }

  function installVerifier() {
    var api = Object.freeze({
      work: CFG.work,
      ver: CFG.ver,
      ts: CFG.ts,
      signature: CFG.signature,
      verify: function () {
        var cssSig = "";
        var domSig = "";
        var fp = document.getElementById("agri-origin-fingerprint");
        try {
          cssSig = getComputedStyle(document.documentElement)
            .getPropertyValue("--agri-signature")
            .replace(/['"]/g, "")
            .trim();
        } catch (e) {
          cssSig = "";
        }
        if (fp && fp.dataset) domSig = fp.dataset.signature || "";
        var ok = cssSig === this.signature && domSig === this.signature;
        try {
          console.log(
            "%c[禾目 AgriGuard] 原创指纹校验：" + (ok ? "完整" : "已被篡改"),
            "color:" + (ok ? "#2e7d4f" : "#a32d2d") + ";font-weight:600;"
          );
          console.log({ cssSignature: cssSig, domSignature: domSig, expected: this.signature });
        } catch (e) {
          /* 控制台不可用 */
        }
        return ok;
      }
    });
    try {
      Object.defineProperty(window, "__agri_guard__", {
        value: api,
        writable: false,
        configurable: false,
        enumerable: false
      });
    } catch (e) {
      /* 极端环境下静默放弃 */
    }
  }

  // ---------------------------------------------------------------------------
  // 预览与状态
  // ---------------------------------------------------------------------------
  var currentObjectUrl = null;

  function setPreview(file) {
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl); // 释放上一张，避免 blob 累积
      currentObjectUrl = null;
    }
    currentObjectUrl = URL.createObjectURL(file);
    preview.src = currentObjectUrl;
    previewWrap.hidden = false;
  }

  function setLoading(on) {
    dropzone.classList.toggle("is-loading", on);
    fileInput.disabled = on;
    dropzone.setAttribute("aria-busy", on ? "true" : "false");
  }

  function setStatusBusy(text) {
    statusEl.textContent = "";
    var wrap = el("span", "status-busy");
    var sp = el("span", "spinner");
    sp.setAttribute("aria-hidden", "true");
    wrap.appendChild(sp);
    wrap.appendChild(el("span", null, text));
    statusEl.appendChild(wrap);
  }

  function setStatusError(text, retryFile) {
    statusEl.textContent = "";
    var span = el("span", "status-error", text);
    statusEl.appendChild(span);
    if (retryFile) {
      var btn = el("button", "btn-link", "重试");
      btn.type = "button";
      btn.addEventListener("click", function () {
        handleFile(retryFile);
      });
      statusEl.appendChild(btn);
    }
  }

  function resetResult() {
    stopSpeech();
    ttsRow.hidden = true;
    lastData = null;
    resultEl.hidden = true;
    verdictEl.textContent = "";
    heatmapBlock.hidden = true;
    heatmapImg.removeAttribute("src");
    detailBlock.textContent = "";
    prescriptionEl.textContent = "";
  }

  // ---------------------------------------------------------------------------
  // 语音朗读（Web Speech API）
  // ---------------------------------------------------------------------------
  // 播报顺序固定：作物名 + 病害名 + 严重程度 + 处方摘要（设计规格 §2.5）。
  // 纪律：任何不可用路径都必须有可见提示（AC-15），不得静默失败。
  var TTS_UNSUPPORTED_MSG = "当前浏览器不支持语音朗读，换用 Chrome 或 Edge 可以听到。";
  var TTS_ERROR_MSG = "朗读失败，请再试一次。";
  var GRADE_SPEECH = { "轻": "轻微", "中": "中等", "重": "严重", "待评估": "待评估" };

  var speechSupported = false;
  try {
    speechSupported = typeof window.speechSynthesis !== "undefined" && typeof window.SpeechSynthesisUtterance !== "undefined";
  } catch (e) {
    speechSupported = false;
  }

  var speechPlaying = false;
  var speechCancelling = false; // cancel() 会触发 onerror(interrupted)，用它区分"主动停止"与"真出错"
  var ttsWarned = false;
  var lastData = null;
  var notSavedNoticeShown = false; // 「未保存」提示每次会话只弹一次

  function buildSpeechText(data) {
    if (!data || data.ok === false) return "";
    var dets = Array.isArray(data.detections) ? data.detections : [];
    var top = dets.length ? dets[0] : null;
    var rx = data.prescription || null;
    var head = top && top.name ? String(top.name) : rx && rx.disease ? String(rx.disease) : "";
    if (!head && !rx) return "";

    var chunks = [];
    if (head) chunks.push(head.replace(/\s*·\s*/g, "，"));
    var grade = data.severity_grade;
    // 健康样本的病害名本身就是「健康」，别再念一遍"植株健康"
    if (grade === "健康") {
      if (!/健康/.test(head)) chunks.push("植株健康");
    } else if (grade) {
      chunks.push("严重程度" + (GRADE_SPEECH[grade] || grade));
    }

    var text = chunks.join("，") + "。";
    if (rx && rx.summary) text += "防治建议：" + String(rx.summary);
    return text;
  }

  function setTtsPlaying(on) {
    speechPlaying = on;
    ttsBtn.classList.toggle("is-playing", on);
    ttsBtn.setAttribute("aria-pressed", on ? "true" : "false");
    ttsBtn.setAttribute("aria-label", on ? "停止朗读" : "朗读本次诊断结论");
    ttsIcon.innerHTML = iconSvg(on ? "volumeOff" : "volume", 20);
    ttsLabel.textContent = on ? "停止朗读" : "朗读结论";
  }

  function stopSpeech() {
    if (!speechSupported) return;
    try {
      speechCancelling = true;
      window.speechSynthesis.cancel();
    } catch (e) {
      /* 忽略 */
    }
    setTtsPlaying(false);
  }

  function startSpeech() {
    var text = buildSpeechText(lastData);
    if (!text) {
      AGRI.toast("本次没有可朗读的结论。", "info");
      return;
    }
    // 进入播放流程即清掉「主动取消」标记：此后收到的任何 onerror 都是真失败，
    // 必须被报出来。否则上一次 stopSpeech() 留下的标记会让本次错误被误判为
    // "用户自己停的"而不给任何提示 —— 那正是 AC-15 禁止的静默失败。
    speechCancelling = false;
    try {
      window.speechSynthesis.cancel();
      var utter = new window.SpeechSynthesisUtterance(text);
      utter.lang = "zh-CN";
      utter.rate = 1;
      utter.pitch = 1;

      // 有些环境「声称支持」语音合成却没有任何可用语音（例如无声卡 / 引擎缺失），
      // 它会立即结束或干脆不发声。用 onstart 判定是否真的开了口：
      // 从未 onstart 就直接 onend ⇒ 等同于不可用，必须给出可见提示（AC-15）。
      var started = false;
      utter.onstart = function () {
        started = true;
      };
      utter.onend = function () {
        var wasCancel = speechCancelling;
        speechCancelling = false;
        setTtsPlaying(false);
        if (!started && !wasCancel) AGRI.toast(TTS_UNSUPPORTED_MSG, "info");
      };
      utter.onerror = function () {
        var wasCancel = speechCancelling;
        speechCancelling = false;
        setTtsPlaying(false);
        if (!wasCancel) AGRI.toast(TTS_ERROR_MSG, "error");
      };

      setTtsPlaying(true);
      window.speechSynthesis.speak(utter);
    } catch (e) {
      speechCancelling = false;
      setTtsPlaying(false);
      AGRI.toast(TTS_ERROR_MSG, "error");
    }
  }

  function warnTtsUnsupported() {
    if (speechSupported || ttsWarned) return;
    ttsWarned = true;
    AGRI.toast(TTS_UNSUPPORTED_MSG, "info");
  }

  function initTts() {
    ttsIcon.innerHTML = iconSvg("volume", 20);
    if (!speechSupported) {
      ttsBtn.disabled = true;
      ttsBtn.setAttribute("aria-label", "当前浏览器不支持语音朗读");
      ttsBtn.setAttribute("aria-pressed", "false");
      warnTtsUnsupported(); // 页面加载即给可见提示，而不是等用户点了才发现没反应
      return;
    }
    ttsBtn.addEventListener("click", function () {
      if (speechPlaying) stopSpeech();
      else startSpeech();
    });
  }

  // ---------------------------------------------------------------------------
  // 请求编排：并发守卫 + 超时 + 陈旧响应丢弃
  // ---------------------------------------------------------------------------
  var inflight = null;
  var requestSeq = 0;

  function handleFile(file) {
    if (!file) return;
    if (!file.type || file.type.indexOf("image/") !== 0) {
      setStatusError("请选择图片文件（JPG / PNG / WEBP / BMP）。", file);
      return;
    }

    if (inflight) inflight.abort(); // 取消上一次未完成的请求
    inflight = new AbortController();
    var seq = ++requestSeq;
    var localSignal = inflight;

    setPreview(file);
    resetResult();
    setStatusBusy("正在校验并诊断图片…");
    setLoading(true);

    var timeoutId = setTimeout(function () {
      if (localSignal) localSignal.abort("timeout");
    }, CFG.requestTimeoutMs);

    var form = new FormData();
    form.append("file", file);

    // 带令牌诊断 → 后端自动写入一条历史（含缩略图）；不带或令牌已失效
    // → 照常诊断、只是不入库，不报错、不中断（Spec §5.1 / AC-10）。
    var headers = {};
    var token = AGRI.getToken();
    if (token) headers.Authorization = "Bearer " + token;

    fetch("/api/v1/predict", {
      method: "POST",
      body: form,
      headers: headers,
      signal: localSignal.signal
    })
      .then(function (r) {
        if (!r.ok) throw new Error("服务返回 " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (seq !== requestSeq) return; // 丢弃陈旧响应
        render(data);
      })
      .catch(function (err) {
        if (seq !== requestSeq) return;
        if (err && err.name === "AbortError") {
          if (err.message === "timeout") {
            setStatusError("诊断超时（超过 " + CFG.requestTimeoutMs / 1000 + " 秒），请重试或换用更小的图片。", file);
          }
          return;
        }
        setStatusError("诊断失败：" + ((err && err.message) || "未知错误"), file);
      })
      .finally(function () {
        clearTimeout(timeoutId);
        if (seq === requestSeq) {
          setLoading(false);
          inflight = null;
        }
      });
  }

  // ---------------------------------------------------------------------------
  // 渲染
  // ---------------------------------------------------------------------------
  // 可信度 / 严重度 pill 的阈值判定只有一份实现（layout.js），
  // 病例库与历史页复用同一套，避免各处再写一份阈值。
  function confidencePill(conf) {
    return AGRI.confidencePill(conf);
  }

  function severityPill(grade) {
    return AGRI.severityPill(grade);
  }

  function lesionPill(ratio) {
    var n = Number(ratio);
    if (!isFinite(n)) return null;
    var pill = el("span", "pill pill-neutral");
    pill.appendChild(el("span", null, "病灶面积"));
    pill.appendChild(el("span", "pill-num", pct(n)));
    return pill;
  }

  function renderVerdict(data) {
    verdictEl.textContent = "";
    var dets = Array.isArray(data.detections) ? data.detections : [];
    var top = dets.length ? dets[0] : null;
    var rx = data.prescription || null;

    var headline = top ? String(top.name) : rx && rx.disease ? String(rx.disease) : "未识别到有效病害";
    verdictEl.appendChild(el("p", "verdict-disease", headline));

    var pills = el("div", "verdict-pills");
    if (top) pills.appendChild(confidencePill(top.confidence));
    pills.appendChild(severityPill(data.severity_grade));
    var lp = lesionPill(data.lesion_ratio);
    if (lp) pills.appendChild(lp);
    verdictEl.appendChild(pills);

    if (rx && rx.summary) verdictEl.appendChild(el("p", "verdict-summary", String(rx.summary)));
  }

  function buildFold(summaryText, iconName, bodyBuilder) {
    var d = el("details", "fold");
    var s = el("summary");
    s.innerHTML = iconSvg(iconName, 16);
    s.appendChild(el("span", null, summaryText));
    d.appendChild(s);
    var body = el("div", "fold-body");
    bodyBuilder(body);
    d.appendChild(body);
    return d;
  }

  function renderDetail(data, dets) {
    detailBlock.textContent = "";

    var others = dets.slice(1);
    if (others.length) {
      detailBlock.appendChild(
        buildFold("其他可能（" + others.length + "）", "chevron", function (body) {
          others.forEach(function (d) {
            var row = el("div", "rank-row");
            row.appendChild(el("span", "rank-name", d && d.name ? String(d.name) : "—"));
            row.appendChild(el("span", "rank-conf", pct(d && d.confidence)));
            body.appendChild(row);
          });
        })
      );
    }

    detailBlock.appendChild(
      buildFold("技术详情", "info", function (body) {
        var dl = el("dl", "kv");

        function kv(label, value, plain) {
          dl.appendChild(el("dt", null, label));
          var dd = el("dd", plain ? "plain" : null, value);
          dl.appendChild(dd);
        }

        var reject = data.ood_reject_threshold != null ? Number(data.ood_reject_threshold) : meta.oodRejectThreshold;
        var warn = data.ood_warn_threshold != null ? Number(data.ood_warn_threshold) : meta.oodWarnThreshold;

        kv(
          "分布相似度",
          num(data.ood_score, 4) +
            (warn != null && reject != null ? "（<" + reject + " 拒识，" + reject + "~" + warn + " 警告）" : "")
        );
        kv("叶片占比", num(data.leaf_ratio, 4));
        kv("背景主色占比", num(data.background_dominant_ratio, 4));
        if (data.lesion_ratio != null) kv("病灶面积占比", num(data.lesion_ratio, 4));
        if (data.latency_ms != null) kv("服务端耗时", num(data.latency_ms, 1) + " ms");
        if (data.model_name) kv("模型权重", String(data.model_name) + (data.model_weight_mb != null ? " · " + data.model_weight_mb + "MB" : ""));
        if (data.device) kv("推理设备", String(data.device), true);
        kv("处方来源", data.prescription_source === "llm" ? "大模型生成" : data.prescription_source === "template" ? "内置模板兜底" : "无", true);

        body.appendChild(dl);
      })
    );
  }

  function renderPrescription(rx) {
    AGRI.renderPrescription(rx, prescriptionEl);
  }

  function renderRejection(data) {
    resultEl.hidden = false;
    verdictEl.textContent = "";
    heatmapBlock.hidden = true;
    heatmapImg.removeAttribute("src");
    detailBlock.textContent = "";
    prescriptionEl.textContent = "";

    var dets = Array.isArray(data.detections) ? data.detections : [];
    var isOod = data.ood_score !== null && data.ood_score !== undefined;
    var notice = el("div", "notice " + (isOod ? "notice-warn" : "notice-danger"));
    var title = el("p", "notice-title");
    title.innerHTML = iconSvg(isOod ? "alert" : "imageOff", 20);
    title.appendChild(el("span", null, isOod ? "模型不确定：这张图可能不在可识别范围内" : "照片不符合拍摄规范"));
    notice.appendChild(title);
    notice.appendChild(el("p", null, String(data.reason || "请重拍后再试。")));
    verdictEl.appendChild(notice);

    // 拒识时仍展示模型的原始判定，供人工参考（但明确标注系统已拒绝采纳）
    if (isOod && dets.length) {
      var ref = el("div", "ref-block");
      ref.appendChild(el("p", null, "模型原始判定（仅供参考，系统已拒绝采纳）"));
      dets.forEach(function (d) {
        var row = el("div", "rank-row");
        row.appendChild(el("span", "rank-name", d && d.name ? String(d.name) : "—"));
        row.appendChild(el("span", "rank-conf", pct(d && d.confidence)));
        ref.appendChild(row);
      });
      var reject = data.ood_reject_threshold != null ? data.ood_reject_threshold : meta.oodRejectThreshold;
      ref.appendChild(
        el(
          "p",
          "ref-note",
          "拒识原因：该图特征与训练分布差异较大" +
            (reject != null ? "（相似度 " + num(data.ood_score, 4) + "，低于拒识阈值 " + reject + "）" : "") +
            "，模型给出的高置信度并不可靠，请勿直接采纳。"
        )
      );
      verdictEl.appendChild(ref);
    }
  }

  function render(data) {
    resultEl.hidden = false;

    if (!data || data.ok === false) {
      renderRejection(data || {});
      return;
    }

    var dets = Array.isArray(data.detections) ? data.detections : [];
    renderVerdict(data);
    renderDetail(data, dets);

    // 语音朗读：有可播报内容才露出入口（拒识 / 无结论时不显示空按钮）
    lastData = data;
    ttsRow.hidden = !buildSpeechText(data);

    if (data.warning) {
      var warn = el("div", "notice notice-warn");
      var t = el("p", "notice-title");
      t.innerHTML = iconSvg("alert", 20);
      t.appendChild(el("span", null, "识别结果仅供参考"));
      warn.appendChild(t);
      warn.appendChild(el("p", null, String(data.warning)));
      verdictEl.appendChild(warn);
    }

    if (data.heatmap_url) {
      heatmapImg.src = String(data.heatmap_url);
      heatmapBlock.hidden = false;
    } else {
      heatmapBlock.hidden = true;
      heatmapImg.removeAttribute("src");
    }

    renderPrescription(data.prescription);

    if (data.prescription_source === "template") {
      var note = el("p", "prescription-source");
      note.textContent =
        "本条处方由内置模板生成（未接入大模型）。接入大模型后，将根据病害与严重程度输出个性化处方。";
      prescriptionEl.appendChild(note);
    }

    // 未登录（或令牌已失效）时后端不落库：明确告知一次，不阻断、不报错（AC-10）
    if ((data.history_id === null || data.history_id === undefined) && !notSavedNoticeShown) {
      notSavedNoticeShown = true;
      AGRI.toast("本次结果未保存，登录后会自动留存。", "info");
    }

    // 出结果后把结论卡带入视野，便于演示时无需手动滚动
    try {
      if (resultEl.scrollIntoView) {
        resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (e) {
      /* 忽略 */
    }
  }

  // ---------------------------------------------------------------------------
  // 事件绑定
  // ---------------------------------------------------------------------------
  dropzone.addEventListener("click", function () {
    fileInput.click();
  });

  dropzone.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      fileInput.click();
    }
  });

  dropzone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  });

  dropzone.addEventListener("dragleave", function () {
    dropzone.classList.remove("is-dragover");
  });

  dropzone.addEventListener("drop", function (e) {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
    var f = e.dataTransfer && e.dataTransfer.files ? e.dataTransfer.files[0] : null;
    if (f) handleFile(f);
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files && fileInput.files[0]) handleFile(fileInput.files[0]);
  });

  // 示例图加载与提交（示例病叶图 / 非支持作物叶片图共用同一逻辑）
  function runSample(btn, url, filename, busyText) {
    btn.disabled = true;
    setStatusBusy(busyText);
    fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error("示例图不可用");
        return r.blob();
      })
      .then(function (blob) {
        handleFile(new File([blob], filename, { type: "image/jpeg" }));
      })
      .catch(function (err) {
        setStatusError("示例图加载失败：" + ((err && err.message) || "未知错误"));
      })
      .finally(function () {
        btn.disabled = false;
      });
  }

  demoBtn.addEventListener("click", function () {
    runSample(
      demoBtn,
      "/static/_demo_leaf_compliant.jpg",
      "_demo_leaf_compliant.jpg",
      "正在加载示例病叶图…"
    );
  });

  // 拒识演示：这张是【非支持作物】（银杏）的真实照片，能进入 OOD 拒识区，
  // 用来展示「系统敢说自己不知道」这一核心能力。
  // 素材来源与授权见 docs/演示素材.md。
  if (oodBtn) {
    oodBtn.addEventListener("click", function () {
      runSample(
        oodBtn,
        "/static/_demo_leaf_ood.jpg",
        "_demo_leaf_ood.jpg",
        "正在加载非支持作物叶片图…"
      );
    });
  }

  // 示例缩略图缺失时优雅降级，不出现破图
  demoThumb.addEventListener("error", function () {
    demoThumb.style.display = "none";
  });

  window.addEventListener("beforeunload", function () {
    if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
    // 离开页面必须掐断朗读，否则部分浏览器会在后台继续播
    if (speechSupported) {
      try {
        window.speechSynthesis.cancel();
      } catch (e) {
        /* 忽略 */
      }
    }
  });

  // ---------------------------------------------------------------------------
  // 启动
  // ---------------------------------------------------------------------------
  installVerifier();
  agriOriginClaim();
  initTts();
  loadMeta();
})();
