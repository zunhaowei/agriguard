const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file");
const demoBtn = document.getElementById("demo-btn");
const preview = document.getElementById("preview");
const status = document.getElementById("status");
const result = document.getElementById("result");
const detectionsEl = document.getElementById("detections");
const heatmapEl = document.getElementById("heatmap");
const heatmapImg = document.getElementById("heatmap-img");
const prescriptionEl = document.getElementById("prescription");

dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.style.borderColor = "#2e7d4f";
});

dropzone.addEventListener("dragleave", () => {
  dropzone.style.borderColor = "#bfe0cc";
});

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

demoBtn.addEventListener("click", () => {
  demoBtn.disabled = true;
  status.textContent = "正在加载示例图…";
  fetch("/static/_demo_leaf_compliant.jpg")
    .then((r) => {
      if (!r.ok) throw new Error("示例图不存在");
      return r.blob();
    })
    .then((blob) => {
      const file = new File([blob], "_demo_leaf_compliant.jpg", { type: "image/jpeg" });
      handleFile(file);
    })
    .catch((err) => {
      status.textContent = "示例图加载失败：" + err.message;
    })
    .finally(() => {
      demoBtn.disabled = false;
    });
});

function handleFile(file) {
  if (!file.type.startsWith("image/")) {
    status.textContent = "请上传图片文件";
    return;
  }
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  result.hidden = true;
  status.textContent = "正在校验图片…";

  const form = new FormData();
  form.append("file", file);
  fetch("/predict", { method: "POST", body: form })
    .then((r) => r.json())
    .then(render)
    .catch((err) => {
      status.textContent = "诊断失败：" + err.message;
    });
}

function render(data) {
  status.textContent = "";

  if (data.ok === false) {
    result.hidden = true;
    heatmapEl.hidden = true;
    heatmapImg.src = "";
    prescriptionEl.innerHTML = "";
    detectionsEl.innerHTML = "";
    const isOod = data.ood_score !== null && data.ood_score !== undefined;
    const title = isOod ? "模型不确定" : "上传不合规";
    const scoreInfo = isOod
      ? ' <span style="color:#64748b;font-size:12px;">(分布相似度 ' +
        data.ood_score.toFixed(2) +
        " / 拒识阈值 0.25)</span>"
      : "";
    status.innerHTML =
      '<span style="color:#a32d2d;">' +
      title +
      "：" +
      escapeHtml(data.reason || "请重试") +
      "</span>" +
      scoreInfo;

    // 方案 B：OOD 拒识时，展示模型的原始 top3 判定，供用户人工参考
    if (isOod && data.detections && data.detections.length) {
      const ref = document.createElement("div");
      ref.style.cssText =
        "margin:12px 0;padding:10px 12px;background:#f1f5f9;border-radius:8px;font-size:12px;color:#475569;";
      let html =
        '<div style="margin-bottom:6px;color:#64748b;font-weight:600;">模型原始判定（仅供参考，系统已拒绝采纳）：</div>';
      data.detections.forEach((d) => {
        html +=
          '<div style="display:flex;justify-content:space-between;padding:2px 0;">' +
          "<span>" +
          escapeHtml(d.name) +
          "</span>" +
          "<span>" +
          (d.confidence * 100).toFixed(1) +
          "%</span></div>";
      });
      html +=
        '<div style="margin-top:6px;color:#94a3b8;">为什么拒识：这张图的特征与训练集差异较大，模型给出的高置信度并不可靠，请勿直接采纳。</div>';
      ref.innerHTML = html;
      status.appendChild(ref);
    }
    return;
  }

  result.hidden = false;

  // 显示分布相似度（OOD 分数）
  const scoreP = document.createElement("p");
  scoreP.style.cssText = "margin:0 0 12px;font-size:12px;color:#64748b;";
  scoreP.textContent = "分布相似度：" + (data.ood_score || 0).toFixed(2) + "（≥0.32 为正常）";
  detectionsEl.appendChild(scoreP);

  // 灰色地带的警告提示
  if (data.warning) {
    const warnP = document.createElement("p");
    warnP.style.cssText = "margin:0 0 12px;font-size:13px;color:#8a6d3b;background:#fff9e6;padding:8px 12px;border-radius:8px;";
    warnP.textContent = data.warning;
    detectionsEl.appendChild(warnP);
  }

  data.detections.forEach((d) => {
    const row = document.createElement("div");
    row.className = "detection";
    row.innerHTML =
      '<span class="name">' +
      escapeHtml(d.name) +
      '</span><span class="conf">' +
      (d.confidence * 100).toFixed(1) +
      "%</span>";
    detectionsEl.appendChild(row);
  });

  if (data.heatmap_url) {
    heatmapImg.src = data.heatmap_url;
    heatmapEl.hidden = false;
  } else {
    heatmapEl.hidden = true;
    heatmapImg.src = "";
  }

  prescriptionEl.innerHTML = "";
  const p = data.prescription;
  if (p) {
    const blocks = [
      ["严重程度", p.severity],
      ["诊断概述", p.summary],
      ["生物防治", p.biological],
      ["化学用药", p.chemical],
      ["日常管理", p.tips],
    ];
    blocks.forEach(([label, text]) => {
      const block = document.createElement("div");
      block.className = "block";
      const isDanger = label === "严重程度" && text !== "健康";
      block.innerHTML =
        '<span class="label">' +
        label +
        '</span><p class="' +
        (isDanger ? "severity-danger" : "") +
        '">' +
        escapeHtml(text) +
        "</p>";
      prescriptionEl.appendChild(block);
    });
  } else {
    prescriptionEl.innerHTML = '<p class="subtitle">未识别到有效病害，请重拍或换一张清晰照片。</p>';
  }
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}