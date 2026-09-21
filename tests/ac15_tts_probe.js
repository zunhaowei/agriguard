/**
 * AC-15 可执行验证探针（Node）。
 *
 * 目的：把「浏览器不支持语音合成时必须给出可见降级提示、且朗读按钮被禁用」
 * 这条 AC 从「仅代码审查」升级为**可执行验证**。
 *
 * 做法：在一个极简 DOM shim 里，真实加载产品源码 `frontend/layout.js` +
 * `frontend/app.js`（不是复制一份逻辑），分别在两个场景下运行：
 *   - supported   : window.speechSynthesis / SpeechSynthesisUtterance 存在
 *   - unsupported : window.speechSynthesis 为 undefined（模拟不支持的环境）
 * 然后读回 #tts-btn 的 disabled 状态与 document.body 中真实生成的提示文案。
 *
 * 说明（诚实标注）：本探针执行的是真实的降级**代码路径**与真实的提示 DOM 生成
 * （layout.js 的 toast），但**不验证真实音频是否发声** —— 无头环境无法验证 TTS
 * 实际播放，这一点仍属未覆盖。
 *
 * 用法： node tests/ac15_tts_probe.js <supported|unsupported> [repoRoot]
 * 输出： 单行 JSON（供 pytest 解析）。
 */

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scenario = (process.argv[2] || "unsupported").toLowerCase();
const repoRoot = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.resolve(__dirname, "..");

const errors = [];

// ---------------------------------------------------------------------------
// 极简 DOM shim
// ---------------------------------------------------------------------------
function makeClassList() {
  const set = new Set();
  return {
    add: function () { [].forEach.call(arguments, (c) => set.add(c)); },
    remove: function () { [].forEach.call(arguments, (c) => set.delete(c)); },
    toggle: function (c, on) {
      const v = on === undefined ? !set.has(c) : !!on;
      if (v) set.add(c); else set.delete(c);
      return v;
    },
    contains: (c) => set.has(c),
  };
}

class FakeNode {
  constructor(tag) {
    this.tagName = String(tag || "").toUpperCase();
    this.nodeName = this.tagName;
    this.nodeType = 1;
    this.children = [];
    this.childNodes = this.children;
    this.parentNode = null;
    this.className = "";
    this.classList = makeClassList();
    this.attributes = Object.create(null);
    this.dataset = {};
    this.style = {};
    this._textContent = "";
    this.disabled = false;
    this.value = "";
    this.id = "";
    this.href = "";
    this.innerHTML = "";
    this.type = "";
  }
  get firstChild() { return this.children[0] || null; }
  get lastChild() { return this.children[this.children.length - 1] || null; }
  get textContent() { return this._textContent; }
  set textContent(v) {
    this._textContent = v === undefined || v === null ? "" : String(v);
    this.children = [];
    this.childNodes = this.children;
  }
  appendChild(c) { if (c) { this.children.push(c); c.parentNode = this; } return c; }
  insertBefore(c, ref) {
    if (!c) return c;
    const i = this.children.indexOf(ref);
    if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
    c.parentNode = this;
    return c;
  }
  removeChild(c) {
    const i = this.children.indexOf(c);
    if (i >= 0) this.children.splice(i, 1);
    if (c) c.parentNode = null;
    return c;
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === "class") this.className = String(v);
  }
  getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; }
  removeAttribute(k) { delete this.attributes[k]; }
  hasAttribute(k) { return k in this.attributes; }
  addEventListener() {}
  removeEventListener() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() {}
  blur() {}
  click() {}
  dispatchEvent() { return true; }
  cloneNode() { return new FakeNode(this.tagName); }
  contains(n) { let p = n; while (p) { if (p === this) return true; p = p.parentNode; } return false; }
}

function collectLeafText(node, out) {
  if (!node) return;
  const kids = node.children || [];
  if (kids.length === 0 && node._textContent) out.push(node._textContent);
  for (const k of kids) collectLeafText(k, out);
}

// ---------------------------------------------------------------------------
// 组装沙箱（vm context 自带 Object/Array/Promise/Math/isFinite 等内置对象）
// ---------------------------------------------------------------------------
const byId = Object.create(null);
const documentShim = {
  body: new FakeNode("body"),
  documentElement: new FakeNode("html"),
  readyState: "loading", // 让 layout.js 把 boot() 推迟到 DOMContentLoaded（不触发）
  getElementById(id) {
    if (!byId[id]) { const n = new FakeNode("div"); n.id = id; byId[id] = n; }
    return byId[id];
  },
  createElement(tag) { return new FakeNode(tag); },
  createTextNode(text) {
    const n = new FakeNode("#text");
    n.nodeType = 3;
    n._textContent = text === undefined || text === null ? "" : String(text);
    return n;
  },
  createDocumentFragment() { return new FakeNode("#fragment"); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  removeEventListener() {},
};

const sandbox = {
  document: documentShim,
  console: { log() {}, warn() {}, error() {}, info() {}, debug() {} },
  // 永不落定的 Promise：既不会触发 .then 分支，也不会产生未处理拒绝
  fetch: function () { return new Promise(function () {}); },
  setTimeout: function () { return 0; },   // 不真正触发，让 toast 节点留在 DOM 里待检
  clearTimeout: function () {},
  setInterval: function () { return 0; },
  clearInterval: function () {},
  getComputedStyle: function () { return { getPropertyValue() { return ""; } }; },
  AbortController: function () { this.signal = {}; this.abort = function () {}; },
  URL: { createObjectURL() { return "blob:x"; }, revokeObjectURL() {} },
  navigator: { userAgent: "node-shim" },
  localStorage: {
    _d: Object.create(null),
    getItem(k) { return k in this._d ? this._d[k] : null; },
    setItem(k, v) { this._d[k] = String(v); },
    removeItem(k) { delete this._d[k]; },
  },
  location: {
    pathname: "/static/index.html",
    href: "http://127.0.0.1/static/index.html",
    search: "",
    replace() {},
  },
  // window === sandbox，故这些宿主 API 也要挂到沙箱本身
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() { return true; },
};
sandbox.window = sandbox; // 浏览器语义：window === 全局对象

if (scenario === "supported") {
  sandbox.speechSynthesis = { cancel() {}, speak() {}, getVoices() { return []; } };
  sandbox.SpeechSynthesisUtterance = function () {};
} else {
  sandbox.speechSynthesis = undefined;       // 模拟不支持
  sandbox.SpeechSynthesisUtterance = undefined;
}

const context = vm.createContext(sandbox);

function run(file) {
  const src = fs.readFileSync(path.join(repoRoot, "frontend", file), "utf8");
  try {
    vm.runInContext(src, context, { filename: file });
  } catch (e) {
    errors.push(file + ": " + (e && e.message ? e.message : String(e)));
  }
}

run("layout.js"); // 提供 window.AGRI（含真实 toast/图标表）
run("app.js");    // 含真实 initTts()

// ---------------------------------------------------------------------------
// 读回结果
// ---------------------------------------------------------------------------
const ttsBtn = byId["tts-btn"] || { disabled: null, attributes: {} };
const textLeaves = [];
collectLeafText(documentShim.body, textLeaves);
const bodyText = textLeaves.join(" | ");
const UNSUPPORTED_MARK = "不支持语音朗读";

process.stdout.write(JSON.stringify({
  scenario,
  speechSupported: typeof sandbox.speechSynthesis !== "undefined" &&
    typeof sandbox.SpeechSynthesisUtterance !== "undefined",
  ttsDisabled: ttsBtn.disabled === true,
  ttsAriaLabel: ttsBtn.attributes["aria-label"] || null,
  ttsAriaPressed: ttsBtn.attributes["aria-pressed"] || null,
  hasUnsupportedMsg: bodyText.indexOf(UNSUPPORTED_MARK) >= 0,
  bodyText,
  agriLoaded: !!sandbox.AGRI,
  errors,
}) + "\n");
