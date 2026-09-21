/**
 * 禾目 AgriGuard · 病例库  agri-guard/v1.0-ext
 * 原创作品 · 2026-09-21 · 禾目团队独立实现
 *
 * 契约：GET /api/v1/cases（Spec §5）→ { ok, crops:[{crop_key,crop_cn,count,classes[]}] }
 * 例图：GET /api/v1/cases/image/{class_key}
 *
 * 说明：索引响应**不含** summary（Spec §5 已锁定该结构），因此卡片只呈现
 * 「例图 + 病害名 + 作物名」三级信息；简介在详情页给出。若后端后续在索引里
 * 追加 summary，本页会自动多渲染一行截断简介，无需改动。
 */
(function () {
  "use strict";

  var AGRI = window.AGRI;
  if (!AGRI) return;

  var PAGE_SIZE = 24;

  var cropList = document.getElementById("crop-list");
  var region = document.getElementById("case-region");
  var searchInput = document.getElementById("case-q");
  var cropSelect = document.getElementById("case-crop");
  var clearBtn = document.getElementById("case-clear");
  var countEl = document.getElementById("case-count");
  var pageSub = document.getElementById("page-sub");

  var state = { crops: [], items: [], crop: "", q: "", shown: PAGE_SIZE };

  // ---------------------------------------------------------------------------
  // 取数
  // ---------------------------------------------------------------------------
  function imageUrl(classKey) {
    return "/api/v1/cases/image/" + encodeURIComponent(classKey);
  }

  function flatten(crops) {
    var items = [];
    crops.forEach(function (group) {
      (group.classes || []).forEach(function (cls) {
        items.push({
          crop_key: group.crop_key,
          crop_cn: group.crop_cn,
          class_key: cls.class_key,
          disease_cn: cls.disease_cn,
          is_healthy: !!cls.is_healthy,
          summary: cls.summary || "" // 索引未返回时为空串
        });
      });
    });
    return items;
  }

  function showSkeleton() {
    AGRI.clear(cropList);
    var side = AGRI.el("div", "skeleton-side");
    for (var i = 0; i < 5; i++) side.appendChild(AGRI.el("div", "skeleton skeleton--line"));
    cropList.appendChild(side);

    AGRI.clear(region);
    var grid = AGRI.el("div", "case-grid");
    for (var j = 0; j < 6; j++) grid.appendChild(AGRI.el("div", "skeleton skeleton--card"));
    region.appendChild(grid);

    searchInput.disabled = true;
    cropSelect.disabled = true;
  }

  function showError(message) {
    AGRI.clear(region);
    region.appendChild(
      AGRI.empty({
        icon: "alert",
        title: "病例库加载失败",
        text: message || "病例库加载失败，请确认服务已启动，然后重试。",
        actionLabel: "重试",
        onAction: function () {
          load();
        }
      })
    );
    searchInput.disabled = true;
    cropSelect.disabled = true;
  }

  function load() {
    showSkeleton();
    AGRI.apiJson("/api/v1/cases")
      .then(function (data) {
        var crops = (data && data.crops) || [];
        state.crops = crops;
        state.items = flatten(crops);
        state.shown = PAGE_SIZE;

        var total = state.items.length;
        pageSub.textContent =
          "共 " + crops.length + " 种作物、" + total + " 个类别（含健康状态），都能看到真实例图和防治要点。";

        searchInput.disabled = false;
        cropSelect.disabled = false;

        if (!crops.length) {
          renderCropList();
          renderSelect();
          AGRI.clear(region);
          region.appendChild(
            AGRI.empty({
              icon: "bookOpen",
              title: "病例库暂时是空的",
              text: "病例库暂时是空的。请确认服务已启动后重试。",
              actionLabel: "重试",
              onAction: function () {
                load();
              }
            })
          );
          countEl.textContent = "";
          return;
        }

        renderCropList();
        renderSelect();
        render();
      })
      .catch(function (err) {
        showError(err && err.message);
        countEl.textContent = "";
      });
  }

  // ---------------------------------------------------------------------------
  // 左栏作物列表 / 下拉（同一份数据，两处联动）
  // ---------------------------------------------------------------------------
  function cropOptions() {
    var opts = [{ key: "", cn: "全部作物", count: state.items.length }];
    state.crops.forEach(function (g) {
      opts.push({ key: g.crop_key, cn: g.crop_cn, count: g.count });
    });
    return opts;
  }

  function renderCropList() {
    AGRI.clear(cropList);
    cropOptions().forEach(function (opt) {
      var b = AGRI.el("button", "crop-item");
      b.type = "button";
      b.setAttribute("aria-pressed", state.crop === opt.key ? "true" : "false");
      b.appendChild(AGRI.el("span", null, opt.cn));
      b.appendChild(AGRI.el("span", "crop-count", String(opt.count)));
      b.addEventListener("click", function () {
        state.crop = opt.key;
        state.shown = PAGE_SIZE;
        syncControls();
        render();
      });
      cropList.appendChild(b);
    });
  }

  function renderSelect() {
    AGRI.clear(cropSelect);
    cropOptions().forEach(function (opt) {
      var o = document.createElement("option");
      o.value = opt.key;
      o.textContent = opt.cn;
      cropSelect.appendChild(o);
    });
    cropSelect.value = state.crop;
  }

  function syncControls() {
    var buttons = cropList.querySelectorAll(".crop-item");
    var opts = cropOptions();
    for (var i = 0; i < buttons.length && i < opts.length; i++) {
      buttons[i].setAttribute("aria-pressed", opts[i].key === state.crop ? "true" : "false");
    }
    cropSelect.value = state.crop;
    searchInput.value = state.q;
  }

  // ---------------------------------------------------------------------------
  // 卡片网格
  // ---------------------------------------------------------------------------
  function filtered() {
    var q = state.q.trim().toLowerCase();
    return state.items.filter(function (it) {
      if (state.crop && it.crop_key !== state.crop) return false;
      if (!q) return true;
      return (
        String(it.disease_cn || "").toLowerCase().indexOf(q) !== -1 ||
        String(it.crop_cn || "").toLowerCase().indexOf(q) !== -1
      );
    });
  }

  function thumbPlaceholder() {
    var box = AGRI.el("div", "case-thumb--empty");
    box.setAttribute("aria-hidden", "true");
    box.innerHTML = AGRI.iconSvg("imageOff", 24);
    return box;
  }

  function buildCard(item) {
    var a = AGRI.el("a", "case-card");
    a.href = "/static/case.html?id=" + encodeURIComponent(item.class_key);

    var img = AGRI.el("img", "case-thumb");
    img.src = imageUrl(item.class_key);
    img.alt = item.crop_cn + " " + item.disease_cn + " 例图";
    img.loading = "lazy";
    img.addEventListener("error", function () {
      if (img.parentNode) img.parentNode.replaceChild(thumbPlaceholder(), img);
    });
    a.appendChild(img);

    var body = AGRI.el("div", "case-body");
    var titleRow = AGRI.el("div", "case-title-row");
    titleRow.appendChild(AGRI.el("h3", "case-name", item.disease_cn));
    if (item.is_healthy) {
      titleRow.appendChild(AGRI.el("span", "pill pill-success", "健康"));
    }
    body.appendChild(titleRow);
    body.appendChild(AGRI.el("span", "case-crop", item.crop_cn));
    if (item.summary) body.appendChild(AGRI.el("p", "case-sum", item.summary));
    a.appendChild(body);

    return a;
  }

  function render() {
    var list = filtered();
    var slice = list.slice(0, state.shown);

    AGRI.clear(region);

    countEl.textContent = "共 " + list.length + " 个类别";

    if (!list.length) {
      region.appendChild(
        AGRI.empty({
          icon: "search",
          title: "没找到相关病害",
          text: "没找到相关病害。换个词试试，或者清空筛选看全部。",
          actionLabel: "清空筛选",
          actionKind: "secondary",
          actionIcon: "x",
          onAction: function () {
            resetFilters();
          }
        })
      );
      return;
    }

    var grid = AGRI.el("div", "case-grid");
    slice.forEach(function (item) {
      grid.appendChild(buildCard(item));
    });
    region.appendChild(grid);

    if (list.length > state.shown) {
      var wrap = AGRI.el("div", "load-more");
      var more = AGRI.button("btn btn-secondary", null, "加载更多", 20);
      more.setAttribute("aria-controls", "case-region");
      more.addEventListener("click", function () {
        state.shown += PAGE_SIZE;
        render();
      });
      wrap.appendChild(more);
      region.appendChild(wrap);
    } else if (list.length > PAGE_SIZE) {
      // 数据已在本地，翻到底就直说，不必再留一个点了没反应的按钮
      var done = AGRI.el("div", "load-more");
      done.appendChild(AGRI.el("p", "empty-note", "已经到底了，共 " + list.length + " 个类别。"));
      region.appendChild(done);
    }
  }

  function resetFilters() {
    state.q = "";
    state.crop = "";
    state.shown = PAGE_SIZE;
    searchInput.value = "";
    syncControls();
    render();
  }

  // ---------------------------------------------------------------------------
  // 事件
  // ---------------------------------------------------------------------------
  var debounceId = null;
  searchInput.addEventListener("input", function () {
    if (debounceId) clearTimeout(debounceId);
    debounceId = setTimeout(function () {
      state.q = searchInput.value;
      state.shown = PAGE_SIZE;
      render();
    }, 300);
  });

  cropSelect.addEventListener("change", function () {
    state.crop = cropSelect.value;
    state.shown = PAGE_SIZE;
    syncControls();
    render();
  });

  clearBtn.addEventListener("click", resetFilters);

  load();
})();
