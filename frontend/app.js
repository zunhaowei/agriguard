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

  // ---------------------------------------------------------------------------
  // 图标（统一描边风格，尺寸仅 16 / 20 / 24 三档；不使用任何 emoji）
  // ---------------------------------------------------------------------------
  var ICON_PATHS = {
    chevron: '<path d="m6 9 6 6 6-6"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    flask: '<path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/><path d="M6.453 15h11.094"/><path d="M8.5 2h7"/>',
    calendar: '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>',
    activity: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    rotate: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    imageOff: '<line x1="2" x2="22" y1="2" y2="22"/><path d="M10.41 10.41a2 2 0 1 1-2.83-2.83"/><line x1="13.5" x2="6" y1="13.5" y2="21"/><path d="M18 12l3 3"/><path d="M3 3l18 18"/>'
  };

  function iconSvg(name, size) {
    var paths = ICON_PATHS[name] || "";
    return (
      '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true">' + paths + "</svg>"
    );
  }

  // ---------------------------------------------------------------------------
  // 小工具
  // ---------------------------------------------------------------------------
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function pct(v) {
    var n = Number(v);
    return isFinite(n) ? (n * 100).toFixed(1) + "%" : "—";
  }

  function num(v, digits) {
    var n = Number(v);
    return isFinite(n) ? n.toFixed(digits === undefined ? 2 : digits) : "—";
  }

  function isHealthyName(name) {
    return typeof name === "string" && name.indexOf("健康") !== -1;
  }

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
    resultEl.hidden = true;
    verdictEl.textContent = "";
    heatmapBlock.hidden = true;
    heatmapImg.removeAttribute("src");
    detailBlock.textContent = "";
    prescriptionEl.textContent = "";
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

    fetch("/api/v1/predict", { method: "POST", body: form, signal: localSignal.signal })
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

  var RX_BLOCKS = [
    { key: "biological", label: "生物防治", icon: "shield" },
    { key: "chemical", label: "化学用药", icon: "flask" },
    { key: "tips", label: "日常管理", icon: "calendar" }
  ];

  function renderPrescription(rx) {
    prescriptionEl.textContent = "";
    if (!rx) {
      prescriptionEl.appendChild(el("p", "empty-note", "未识别到有效病害，请重拍或换一张清晰照片。"));
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
      prescriptionEl.appendChild(block);
    });
    if (!prescriptionEl.childNodes.length) {
      prescriptionEl.appendChild(el("p", "empty-note", "本次未返回处方内容。"));
    }
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

  demoBtn.addEventListener("click", function () {
    demoBtn.disabled = true;
    setStatusBusy("正在加载示例病叶图…");
    fetch("/static/_demo_leaf_compliant.jpg")
      .then(function (r) {
        if (!r.ok) throw new Error("示例图不可用");
        return r.blob();
      })
      .then(function (blob) {
        var f = new File([blob], "_demo_leaf_compliant.jpg", { type: "image/jpeg" });
        handleFile(f);
      })
      .catch(function (err) {
        setStatusError("示例图加载失败：" + ((err && err.message) || "未知错误"));
      })
      .finally(function () {
        demoBtn.disabled = false;
      });
  });

  // 示例缩略图缺失时优雅降级，不出现破图
  demoThumb.addEventListener("error", function () {
    demoThumb.style.display = "none";
  });

  window.addEventListener("beforeunload", function () {
    if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
  });

  // ---------------------------------------------------------------------------
  // 启动
  // ---------------------------------------------------------------------------
  installVerifier();
  agriOriginClaim();
  loadMeta();
})();
