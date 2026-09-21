/**
 * 禾目 AgriGuard · 病例详情  agri-guard/v1.0-ext
 * 原创作品 · 2026-09-21 · 禾目团队独立实现
 *
 * 契约：GET /api/v1/cases/{class_key}（Spec §5）
 *   → { ok, class_key, crop_key, crop_cn, disease_cn, is_healthy,
 *       summary, symptoms[], prevention[], image_url }
 * 例图直接用响应的 image_url（后端已完成百分号编码，前端不得自行拼接，
 * 否则 Corn_(maize)___Cercospora… 这类含空格与括号的类别键会断链）。
 */
(function () {
  "use strict";

  var AGRI = window.AGRI;
  if (!AGRI) return;

  var root = document.getElementById("case-root");

  function queryId() {
    var raw = "";
    try {
      raw = new URLSearchParams(location.search).get("id") || "";
    } catch (e) {
      raw = "";
    }
    return raw.trim();
  }

  function showSkeleton() {
    AGRI.clear(root);
    var hero = AGRI.el("section", "case-hero");
    hero.appendChild(AGRI.el("div", "skeleton skeleton--card"));

    var text = AGRI.el("div", "skeleton-stack");
    text.appendChild(AGRI.el("div", "skeleton skeleton--title"));
    text.appendChild(AGRI.el("div", "skeleton skeleton--line"));
    text.appendChild(AGRI.el("div", "skeleton skeleton--line"));
    text.appendChild(AGRI.el("div", "skeleton skeleton--line"));
    hero.appendChild(text);
    root.appendChild(hero);
  }

  function showNotFound() {
    AGRI.clear(root);
    document.title = "找不到这个病例 · 禾目 AgriGuard";
    root.appendChild(
      AGRI.empty({
        icon: "imageOff",
        title: "找不到这个病例",
        text: "找不到这个病例。它可能已被移除，或者链接不完整。",
        actionLabel: "返回病例库",
        actionIcon: "arrowLeft",
        onAction: function () {
          location.href = "/static/cases.html";
        }
      })
    );
  }

  function defList(items) {
    if (!items || !items.length) {
      return AGRI.el("p", "empty-note", "暂无更多记录。");
    }
    var ul = AGRI.el("ul", "def-list");
    items.forEach(function (text) {
      ul.appendChild(AGRI.el("li", null, text));
    });
    return ul;
  }

  function card(title, content) {
    var section = AGRI.el("section", "card");
    section.appendChild(AGRI.el("h2", "card-title", title));
    section.appendChild(content);
    return section;
  }

  function render(data) {
    AGRI.clear(root);
    document.title = data.disease_cn + " · " + data.crop_cn + " · 禾目 AgriGuard";

    var hero = AGRI.el("section", "case-hero");

    var img = AGRI.el("img", "case-hero-img");
    img.src = data.image_url;
    img.alt = data.crop_cn + " " + data.disease_cn + " 例图";
    img.addEventListener("error", function () {
      var box = AGRI.el("div", "case-thumb--empty");
      box.setAttribute("aria-hidden", "true");
      box.innerHTML = AGRI.iconSvg("imageOff", 24);
      if (img.parentNode) img.parentNode.replaceChild(box, img);
    });
    hero.appendChild(img);

    var body = AGRI.el("div", "case-hero-body");
    body.appendChild(AGRI.el("p", "case-hero-crop", data.crop_cn));

    var titleRow = AGRI.el("div", "case-title-row");
    titleRow.appendChild(AGRI.el("h1", "case-hero-title", data.disease_cn));
    titleRow.appendChild(
      data.is_healthy
        ? AGRI.el("span", "pill pill-success", "健康")
        : AGRI.el("span", "pill pill-neutral", "病害")
    );
    body.appendChild(titleRow);

    if (data.summary) body.appendChild(AGRI.el("p", "case-hero-sum", data.summary));

    var cta = AGRI.link("btn btn-primary", "/static/index.html", "camera", "拍一张照片，诊断我的作物", 20);
    body.appendChild(cta);

    hero.appendChild(body);
    root.appendChild(hero);

    root.appendChild(card("主要症状", defList(data.symptoms)));
    root.appendChild(card("防治要点", defList(data.prevention)));
  }

  var classKey = queryId();
  if (!classKey) {
    showNotFound();
    return;
  }

  showSkeleton();
  AGRI.apiJson("/api/v1/cases/" + encodeURIComponent(classKey))
    .then(function (data) {
      if (!data || data.ok === false || !data.class_key) {
        showNotFound();
        return;
      }
      render(data);
    })
    .catch(function (err) {
      if (err && err.status === 404) {
        showNotFound();
        return;
      }
      AGRI.clear(root);
      root.appendChild(
        AGRI.empty({
          icon: "alert",
          title: "病例加载失败",
          text:
            err && err.status === 0
              ? err.message
              : "病例加载失败，请确认服务已启动，然后重试。",
          actionLabel: "重试",
          onAction: function () {
            location.reload();
          }
        })
      );
    });
})();
