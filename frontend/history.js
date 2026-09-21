/**
 * 禾目 AgriGuard · 诊断历史  agri-guard/v1.0-ext
 * 原创作品 · 2026-09-21 · 禾目团队独立实现
 *
 * 契约：Spec §5
 *   GET    /api/v1/history?limit&offset&crop&q   → { ok, total, items[] }
 *   GET    /api/v1/history/{id}                  → { ok, item{…含处方…} }
 *   GET    /api/v1/history/{id}/thumb?kind=      → image/jpeg
 *   DELETE /api/v1/history/{id}                  → { ok }
 * 全部端点都需要 Authorization，且**先判定登录再渲染**（避免闪一屏空列表）。
 *
 * 【缩略图为什么要走 fetch + blob】
 * 缩略图端点在认证保护之下，<img src> 不会带上 Authorization 头，
 * 直接用 src 必然 401。因此统一 fetch → blob → objectURL，并在
 * 删除记录 / 离开页面时 revoke，避免 blob 累积。
 */
(function () {
  "use strict";

  var AGRI = window.AGRI;
  if (!AGRI) return;

  var PAGE = 20;
  var GUARD_NEXT = "history.html";

  var region = document.getElementById("hist-region");
  var loadMoreBox = document.getElementById("hist-loadmore");
  var cropSelect = document.getElementById("hist-crop");
  var searchInput = document.getElementById("hist-q");
  var clearBtn = document.getElementById("hist-clear");
  var countEl = document.getElementById("hist-count");

  var state = { items: [], total: 0, crop: "", q: "", loading: false };
  var thumbCache = {};

  // ---------------------------------------------------------------------------
  // 缩略图
  // ---------------------------------------------------------------------------
  function thumbKey(id, kind) {
    return id + ":" + kind;
  }

  function needAuthHeaders() {
    var headers = {};
    var token = AGRI.getToken();
    if (token) headers.Authorization = "Bearer " + token;
    return headers;
  }

  function loadThumbUrl(id, kind) {
    var key = thumbKey(id, kind);
    if (thumbCache[key]) return Promise.resolve(thumbCache[key]);
    var url = "/api/v1/history/" + id + "/thumb?kind=" + encodeURIComponent(kind);
    return fetch(url, { headers: needAuthHeaders() }).then(function (res) {
      if (res.status === 401) {
        AGRI.redirectToLogin(GUARD_NEXT);
        throw new Error("登录状态已过期");
      }
      if (!res.ok) throw new Error("这条记录没有保存该图。");
      return res.blob();
    }).then(function (blob) {
      var obj = URL.createObjectURL(blob);
      thumbCache[key] = obj;
      return obj;
    });
  }

  function releaseThumb(id) {
    ["original", "heatmap"].forEach(function (kind) {
      var key = thumbKey(id, kind);
      if (thumbCache[key]) {
        URL.revokeObjectURL(thumbCache[key]);
        delete thumbCache[key];
      }
    });
  }

  function releaseAllThumbs() {
    Object.keys(thumbCache).forEach(function (key) {
      URL.revokeObjectURL(thumbCache[key]);
      delete thumbCache[key];
    });
  }

  function thumbPlaceholder() {
    var box = AGRI.el("div", "rec-thumb--empty");
    box.setAttribute("aria-hidden", "true");
    box.innerHTML = AGRI.iconSvg("imageOff", 16);
    return box;
  }

  // ---------------------------------------------------------------------------
  // 文案
  // ---------------------------------------------------------------------------
  function titleText(item) {
    var crop = item.crop_cn || "";
    var disease = item.disease_cn || "";
    if (crop && disease) return crop + " · " + disease;
    return crop || disease || "未识别到有效病害";
  }

  // ---------------------------------------------------------------------------
  // 区域态
  // ---------------------------------------------------------------------------
  function showSkeleton() {
    AGRI.clear(region);
    var list = AGRI.el("div", "rec-list");
    for (var i = 0; i < 4; i++) {
      var row = AGRI.el("div", "skeleton-row");
      row.appendChild(AGRI.el("div", "skeleton skeleton--thumb"));
      var stack = AGRI.el("div", "skeleton-stack");
      stack.appendChild(AGRI.el("div", "skeleton skeleton--title"));
      stack.appendChild(AGRI.el("div", "skeleton skeleton--line"));
      row.appendChild(stack);
      list.appendChild(row);
    }
    region.appendChild(list);
  }

  function showError(message) {
    AGRI.clear(region);
    var box = AGRI.el("div", "alert alert-error");
    box.setAttribute("role", "alert");
    box.innerHTML = AGRI.iconSvg("alert", 20);
    box.appendChild(AGRI.el("span", null, message || "记录加载失败，可能是服务暂时不可用。"));
    var retry = AGRI.button("btn btn-secondary", null, "重试", 20);
    retry.addEventListener("click", function () {
      fetchPage(true);
    });
    box.appendChild(retry);
    region.appendChild(box);
    AGRI.clear(loadMoreBox);
    countEl.textContent = "";
  }

  function filtered() {
    return !!state.q || !!state.crop;
  }

  function showEmpty() {
    AGRI.clear(region);
    AGRI.clear(loadMoreBox);
    if (state.total === 0 && !filtered()) {
      region.appendChild(
        AGRI.empty({
          icon: "clock",
          title: "还没有诊断记录",
          text: "还没有诊断记录。上传一张病叶照片，结果就会自动留在这里。",
          actionLabel: "去诊断",
          actionIcon: "camera",
          onAction: function () {
            location.href = "/static/index.html";
          }
        })
      );
      return;
    }
    region.appendChild(
      AGRI.empty({
        icon: "search",
        title: "没有符合条件的记录",
        text: "没有符合条件的记录。换个关键词试试，或者点「清除」看全部。",
        actionLabel: "清除筛选",
        actionKind: "secondary",
        actionIcon: "x",
        onAction: resetFilters
      })
    );
  }

  function updateCount() {
    countEl.textContent = "共 " + state.total + " 条记录";
  }

  function renderLoadMore() {
    AGRI.clear(loadMoreBox);
    if (state.items.length >= state.total) {
      if (state.total > PAGE) {
        var done = AGRI.el("div", "load-more");
        done.appendChild(AGRI.el("p", "empty-note", "已经到底了，共 " + state.total + " 条记录。"));
        loadMoreBox.appendChild(done);
      }
      return;
    }
    var wrap = AGRI.el("div", "load-more");
    var btn = AGRI.button("btn btn-secondary", null, "加载更多", 20);
    btn.setAttribute("aria-controls", "hist-region");
    btn.addEventListener("click", function () {
      AGRI.setBusy(btn, true, "正在加载…");
      // 失败路径由 fetchPage 统一处理（toast + 恢复按钮），此处不重复兜底
      fetchPage(false);
    });
    wrap.appendChild(btn);
    loadMoreBox.appendChild(wrap);
  }

  // ---------------------------------------------------------------------------
  // 行
  // ---------------------------------------------------------------------------
  function buildRow(item) {
    var row = AGRI.el("div", "rec-row is-clickable");
    row.setAttribute("data-id", String(item.id));

    if (item.has_thumb) {
      var img = AGRI.el("img", "rec-thumb");
      img.alt = "";
      img.addEventListener("error", function () {
        if (img.parentNode) img.parentNode.replaceChild(thumbPlaceholder(), img);
      });
      row.appendChild(img);
      loadThumbUrl(item.id, "original")
        .then(function (url) {
          img.src = url;
        })
        .catch(function () {
          if (img.parentNode) img.parentNode.replaceChild(thumbPlaceholder(), img);
        });
    } else {
      row.appendChild(thumbPlaceholder());
    }

    var main = AGRI.el("div", "rec-main");
    var titleLine = AGRI.el("div", "rec-title");
    titleLine.appendChild(AGRI.el("span", "rec-name", titleText(item)));
    main.appendChild(titleLine);

    var sub = AGRI.el("div", "rec-sub");
    var timeItem = AGRI.el("span", "rec-sub-item");
    timeItem.innerHTML = AGRI.iconSvg("calendar", 16);
    timeItem.appendChild(AGRI.el("span", null, AGRI.fmtDateTime(item.created_at)));
    sub.appendChild(timeItem);

    if (item.is_ood) {
      var oodItem = AGRI.el("span", "rec-sub-item");
      oodItem.innerHTML = AGRI.iconSvg("alert", 16);
      oodItem.appendChild(AGRI.el("span", null, "当时模型不确定，已拒识"));
      sub.appendChild(oodItem);
    }
    main.appendChild(sub);
    row.appendChild(main);

    var meta = AGRI.el("div", "rec-meta");
    meta.appendChild(AGRI.severityPill(item.severity_grade));
    meta.appendChild(AGRI.confidencePill(item.confidence));
    row.appendChild(meta);

    var actions = AGRI.el("div", "rec-actions");
    var viewBtn = AGRI.button("btn btn-icon", "info", null, 20);
    viewBtn.setAttribute("aria-label", "查看详情：" + titleText(item));
    viewBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      openDetail(item);
    });
    var delBtn = AGRI.button("btn btn-icon is-danger", "trash", null, 20);
    delBtn.setAttribute("aria-label", "删除记录：" + titleText(item));
    delBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      confirmDelete(item, row);
    });
    actions.appendChild(viewBtn);
    actions.appendChild(delBtn);
    row.appendChild(actions);

    row.addEventListener("click", function () {
      openDetail(item);
    });

    return row;
  }

  function appendRows(items) {
    var list = region.querySelector(".rec-list");
    if (!list) {
      AGRI.clear(region);
      list = AGRI.el("div", "rec-list");
      region.appendChild(list);
    }
    items.forEach(function (item) {
      list.appendChild(buildRow(item));
    });
  }

  // ---------------------------------------------------------------------------
  // 取数
  // ---------------------------------------------------------------------------
  function fetchPage(reset) {
    if (state.loading) return Promise.resolve();
    state.loading = true;
    if (reset) {
      state.items = [];
      showSkeleton();
      AGRI.clear(loadMoreBox);
    }
    var offset = reset ? 0 : state.items.length;
    var parts = ["limit=" + PAGE, "offset=" + offset];
    if (state.crop) parts.push("crop=" + encodeURIComponent(state.crop));
    if (state.q) parts.push("q=" + encodeURIComponent(state.q));

    return AGRI.apiJson("/api/v1/history?" + parts.join("&"), { auth: "required" })
      .then(function (data) {
        state.loading = false;
        var items = (data && data.items) || [];
        state.total = data && typeof data.total === "number" ? data.total : items.length;
        if (reset) {
          state.items = items;
          AGRI.clear(region);
          if (!items.length) {
            updateCount();
            showEmpty();
            return;
          }
          var list = AGRI.el("div", "rec-list");
          region.appendChild(list);
          items.forEach(function (item) {
            list.appendChild(buildRow(item));
          });
        } else {
          state.items = state.items.concat(items);
          appendRows(items);
        }
        updateCount();
        renderLoadMore();
      })
      .catch(function (err) {
        state.loading = false;
        if (err && err.status === 401) return; // 已跳登录页
        var message = (err && err.message) || "记录加载失败，可能是服务暂时不可用。";
        if (reset) {
          showError(message);
        } else {
          // 「加载更多」失败不能把已经看到的记录清空
          AGRI.toast(message, "error");
          renderLoadMore();
        }
      });
  }

  // ---------------------------------------------------------------------------
  // 详情弹层
  // ---------------------------------------------------------------------------
  function openDetail(brief) {
    AGRI.openDialog({
      title: "诊断详情",
      sub: AGRI.fmtDateTime(brief.created_at),
      closeLabel: "关闭详情",
      buildBody: function (body) {
        var stack = AGRI.el("div", "dialog-stack");
        stack.appendChild(AGRI.el("div", "skeleton skeleton--card"));
        var lines = AGRI.el("div", "skeleton-stack");
        lines.appendChild(AGRI.el("div", "skeleton skeleton--line"));
        lines.appendChild(AGRI.el("div", "skeleton skeleton--line"));
        stack.appendChild(lines);
        body.appendChild(stack);
        fillDetail(body, brief);
      },
      buildFoot: function (foot, close) {
        var btn = AGRI.button("btn btn-secondary", null, "关闭", 20);
        btn.addEventListener("click", close);
        foot.appendChild(btn);
      }
    });
  }

  /** 图片区：有缩略图时给出「原图 / 热力图」切换，无缩略图时说明原因。 */
  function buildFigure(item) {
    var figure = AGRI.el("div");

    if (!item.has_thumb) {
      figure.appendChild(AGRI.el("p", "empty-note", "这条记录没有保存预览图。"));
      return figure;
    }

    var img = AGRI.el("img", "heatmap-img");
    img.alt = titleText(item) + " 的诊断图片";
    figure.appendChild(img);

    var kinds = [
      { key: "original", label: "原图" },
      { key: "heatmap", label: "热力图" }
    ];
    var tabs = AGRI.el("div", "tabs");
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", "图片类型");

    var tabBtns = [];
    var missingNote = AGRI.el("p", "empty-note", "这条记录没有保存热力图。");
    missingNote.hidden = true;

    function selectKind(kind) {
      kinds.forEach(function (k, index) {
        tabBtns[index].setAttribute("aria-selected", k.key === kind ? "true" : "false");
      });
      missingNote.hidden = true;
      img.removeAttribute("src");
      loadThumbUrl(item.id, kind)
        .then(function (url) {
          img.src = url;
        })
        .catch(function () {
          missingNote.hidden = false;
        });
    }

    kinds.forEach(function (kind, index) {
      var b = AGRI.el("button", "tab", kind.label);
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", "false");
      b.addEventListener("click", function () {
        selectKind(kind.key);
      });
      tabBtns[index] = b;
      tabs.appendChild(b);
    });

    figure.appendChild(tabs);
    figure.appendChild(missingNote);

    // 有热力图就默认展示热力图（承载信息更多），否则退回原图
    loadThumbUrl(item.id, "heatmap")
      .then(function () {
        selectKind("heatmap");
      })
      .catch(function () {
        selectKind("original");
      });

    return figure;
  }

  function fillDetail(body, brief) {
    AGRI.apiJson("/api/v1/history/" + brief.id, { auth: "required" })
      .then(function (data) {
        var item = (data && data.item) || {};
        AGRI.clear(body);
        var stack = AGRI.el("div", "dialog-stack");

        stack.appendChild(buildFigure(item));

        // ---- 结论 ----
        var verdict = AGRI.el("div", "verdict");
        verdict.appendChild(AGRI.el("p", "verdict-disease", titleText(item)));
        var pills = AGRI.el("div", "verdict-pills");
        pills.appendChild(AGRI.confidencePill(item.confidence));
        pills.appendChild(AGRI.severityPill(item.severity_grade));
        if (item.lesion_ratio !== null && item.lesion_ratio !== undefined) {
          var lesion = AGRI.el("span", "pill pill-neutral");
          lesion.appendChild(AGRI.el("span", null, "病灶面积"));
          lesion.appendChild(AGRI.el("span", "pill-num", AGRI.pct(item.lesion_ratio)));
          pills.appendChild(lesion);
        }
        if (item.is_ood) pills.appendChild(AGRI.el("span", "pill pill-warn", "已拒识"));
        verdict.appendChild(pills);
        if (item.rejected_reason) {
          verdict.appendChild(AGRI.el("p", "verdict-summary", item.rejected_reason));
        }
        stack.appendChild(verdict);

        // ---- 处方 ----
        var rx = AGRI.el("div", "prescription");
        AGRI.renderPrescription(item.prescription, rx);
        stack.appendChild(rx);
        if (item.prescription_source === "template") {
          rx.appendChild(
            AGRI.el("p", "prescription-source", "本条处方由内置模板生成（当时未接入大模型）。")
          );
        } else if (item.prescription_source === "llm") {
          rx.appendChild(AGRI.el("p", "prescription-source", "本条处方由大模型生成。"));
        }

        body.appendChild(stack);
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        AGRI.clear(body);
        var box = AGRI.el("div", "alert alert-error");
        box.setAttribute("role", "alert");
        box.innerHTML = AGRI.iconSvg("alert", 20);
        box.appendChild(AGRI.el("span", null, (err && err.message) || "详情加载失败，请稍后再试。"));
        body.appendChild(box);
      });
  }

  // ---------------------------------------------------------------------------
  // 删除确认
  // ---------------------------------------------------------------------------
  function confirmDelete(brief, row) {
    AGRI.openDialog({
      title: "确定删除这条记录？",
      sub: AGRI.fmtDateTime(brief.created_at),
      closeLabel: "取消删除",
      buildBody: function (body) {
        body.appendChild(
          AGRI.el("p", "empty-note", "删除后就找不回来了，照片和处方都会一起清掉。")
        );
      },
      buildFoot: function (foot, close) {
        var cancel = AGRI.button("btn btn-ghost", null, "取消", 20);
        cancel.addEventListener("click", close);

        var del = AGRI.button("btn btn-danger", "trash", "删除", 20);
        del.addEventListener("click", function () {
          AGRI.setBusy(del, true, "正在删除…");
          AGRI.apiJson("/api/v1/history/" + brief.id, { method: "DELETE", auth: "required" })
            .then(function () {
              close();
              releaseThumb(brief.id);
              if (row && row.parentNode) row.parentNode.removeChild(row);
              state.total = Math.max(0, state.total - 1);
              state.items = state.items.filter(function (it) {
                return it.id !== brief.id;
              });
              updateCount();
              AGRI.toast("已删除这条记录", "success");
              if (!state.items.length) showEmpty();
              else renderLoadMore();
            })
            .catch(function (err) {
              AGRI.setBusy(del, false);
              AGRI.toast((err && err.message) || "删除失败，请稍后再试", "error");
            });
        });
        foot.appendChild(cancel);
        foot.appendChild(del);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // 筛选
  // ---------------------------------------------------------------------------
  function resetFilters() {
    state.crop = "";
    state.q = "";
    cropSelect.value = "";
    searchInput.value = "";
    fetchPage(true);
  }

  var debounceId = null;
  searchInput.addEventListener("input", function () {
    if (debounceId) clearTimeout(debounceId);
    debounceId = setTimeout(function () {
      state.q = searchInput.value.trim();
      fetchPage(true);
    }, 300);
  });

  cropSelect.addEventListener("change", function () {
    state.crop = cropSelect.value;
    fetchPage(true);
  });

  clearBtn.addEventListener("click", resetFilters);

  window.addEventListener("beforeunload", releaseAllThumbs);

  // ---------------------------------------------------------------------------
  // 启动：先判定登录，再渲染（避免未登录时先闪一屏空列表）
  // ---------------------------------------------------------------------------
  AGRI.guard(GUARD_NEXT).then(function (user) {
    if (!user) return; // 已触发跳转登录页

    // 作物下拉选项来自 /api/v1/meta（前端不硬编码作物清单）
    AGRI.apiJson("/api/v1/meta")
      .then(function (meta) {
        var crops = (meta && meta.supported_crops) || [];
        crops.forEach(function (cn) {
          var opt = document.createElement("option");
          opt.value = cn;
          opt.textContent = cn;
          cropSelect.appendChild(opt);
        });
        cropSelect.disabled = false;
      })
      .catch(function () {
        cropSelect.disabled = true; // 下拉不可用不阻断列表浏览
      });

    fetchPage(true);
  });
})();
