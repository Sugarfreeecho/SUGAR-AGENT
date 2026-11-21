const API = "/api/sugar-assistant";
const MODES = [
  { id: "private", label: "私聊" },
  { id: "group", label: "群聊" },
  { id: "comment", label: "评论" },
];
const state = { personaMode: "private", data: {} };

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

async function api(path, options) {
  const res = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function ago(ts) {
  if (!ts) return "—";
  const diff = Date.now() / 1000 - Number(ts);
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

function chip(text, tone) {
  const node = el("span", `chip ${tone || ""}`, text);
  return node;
}

function row(key, value) {
  const wrap = el("div", "row");
  wrap.append(el("span", "k", key));
  const v = el("span", "v");
  if (typeof value === "string") v.textContent = value;
  else v.append(value);
  wrap.append(v);
  return wrap;
}

function card(title, hint) {
  const box = el("div", "card");
  const h = el("h2", "", title);
  if (hint) h.append(el("span", "hint", hint));
  box.append(h);
  return box;
}

function empty(text) {
  return el("div", "empty", text);
}

/* ---------------------------------------------------------------- 概览 */
function renderOverview(status) {
  const pane = $("#pane-overview");
  pane.replaceChildren();

  const core = card("运行", "Core 与通道");
  const health = !status.core ? ["插件未运行", "bad"] :
    status.channels.some((c) => c.enabled && !c.running) ? ["部分通道未连接", "warn"] : ["正常", "ok"];
  core.append(row("状态", chip(health[0], health[1])));
  core.append(row("已运行", status.uptime ? `${Math.floor(status.uptime / 60)} 分钟` : "—"));
  core.append(row("会话", String(status.conversations ?? 0)));
  for (const warning of status.warnings || []) {
    const line = row("提示", chip(warning, "warn"));
    core.append(line);
  }
  pane.append(core);

  const channels = card("通道");
  if (!status.channels.length) channels.append(empty("还没有配置通道"));
  for (const ch of status.channels) {
    const tone = !ch.enabled ? "" : ch.running ? "ok" : "warn";
    const label = !ch.enabled ? "已停用" : ch.running ? "运行中" : "未连接";
    channels.append(row(ch.name, chip(label, tone)));
  }
  const web = status.web;
  if (web) {
    const label = !web.enabled ? "已停用" : web.available ? "可用" : (web.reason || "不可用");
    const tone = !web.enabled ? "" : web.available ? "ok" : "warn";
    channels.append(row("飞书 · 浏览器兜底", chip(label, tone)));
    const last = (web.last || []).slice(-1)[0];
    if (last) channels.append(row("最近一次", `${last.status}${last.detail ? " · " + last.detail : ""}`));
  }
  pane.append(channels);

  const persona = status.persona || {};
  const p = card("人设");
  p.append(row("名字", persona.name || "未设置"));
  p.append(row("风格", (persona.tone || "未设置").slice(0, 40)));
  pane.append(p);
}

/* ---------------------------------------------------------------- 对话 */
const chatFilter = { kind: "all", q: "" };

function chatKind(item) {
  if (item.kind) return item.kind;
  return /^(群聊|小Sugar群聊)/.test(String(item.title || "")) ? "group" : "p2p";
}

function chatId(item) {
  if (item.chat_id) return item.chat_id;
  const parts = String(item.key || "").split(":");
  return parts.length >= 3 ? parts.slice(2).join(":") : "";
}

function chatName(item) {
  const explicit = String(item.chat_name || "").trim();
  if (explicit) return explicit;
  const title = String(item.title || "");
  const modern = title.match(/^(?:群聊|私聊)（(.+)）$/);
  if (modern && !/^[0-9a-f]{6,}$/i.test(modern[1])) return modern[1];
  const legacy = title.match(/^小Sugar群聊-(.+)$/);
  if (legacy && !/^[0-9a-f]{6,}$/i.test(legacy[1])) return legacy[1];
  return "";
}

function chatLabel(item) {
  const kind = chatKind(item) === "group" ? "群聊" : "私聊";
  const name = chatName(item);
  return name ? `${kind}（${name}）` : kind;
}

function renderChats(data) {
  const pane = $("#pane-chats");
  pane.replaceChildren();
  const items = data.items || [];

  const counts = {
    all: items.length,
    group: items.filter((i) => chatKind(i) === "group").length,
    p2p: items.filter((i) => chatKind(i) !== "group").length,
  };

  const controls = el("div", "card");
  const search = el("input");
  search.placeholder = "搜索对话 / chat_id";
  search.value = chatFilter.q;
  search.addEventListener("input", () => { chatFilter.q = search.value.trim(); renderChats(data); });
  controls.append(search);

  const seg = el("div", "seg");
  seg.style.marginTop = "8px";
  for (const [key, label] of [["all", `全部 ${counts.all}`], ["group", `群聊 ${counts.group}`], ["p2p", `私聊 ${counts.p2p}`]]) {
    const b = el("button", chatFilter.kind === key ? "on" : "", label);
    b.addEventListener("click", () => { chatFilter.kind = key; renderChats(data); });
    seg.append(b);
  }
  controls.append(seg);
  pane.append(controls);

  const needle = chatFilter.q.toLowerCase();
  const visible = items.filter((item) => {
    if (chatFilter.kind === "group" && chatKind(item) !== "group") return false;
    if (chatFilter.kind === "p2p" && chatKind(item) === "group") return false;
    if (!needle) return true;
    return [item.title, chatId(item), item.session_id].some((v) => String(v || "").toLowerCase().includes(needle));
  });

  const box = el("div", "card");
  if (!visible.length) {
    box.append(empty(items.length ? "没有匹配的对话" : "还没有对话"));
  }
  for (const item of visible) {
    const line = el("div", "chatitem");

    const head = el("div", "chathead");
    head.append(el("span", "chattitle", chatLabel(item)));
    const time = el("span", "chattime", ago(item.last_used));
    head.append(time);
    line.append(head);

    const meta = el("div", "m");
    const parts = String(item.key || "").split(":");
    meta.append(el("span", "", `${parts[0] || "?"} · ${item.identity === "user" ? "本人" : "机器人"}`), " · ",
      el("span", "mono", String(chatId(item)).slice(0, 14)), " · ",
      el("span", "", "会话 "), el("span", "mono", String(item.session_id || "").slice(0, 8)));
    line.append(meta);

    line.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(chatId(item) || item.key || ""); } catch (_) {}
      time.textContent = "已复制";
      setTimeout(() => { time.textContent = ago(item.last_used); }, 1200);
    });
    box.append(line);
  }
  pane.append(box);
}

/* ---------------------------------------------------------------- 人设 */
function personaData() {
  const persona = state.data.persona || {};
  return { prompt: persona.prompt || "", modes: persona.modes || {} };
}

function modeBlock(mode) {
  const data = personaData();
  const cfg = data.modes[mode] || {};
  const lines = [];
  if (cfg.identity) lines.push(`你的身份：${cfg.identity}`);
  if (cfg.tone) lines.push(`说话风格：${cfg.tone}`);
  const rules = String(cfg.rules || "").split("\n").filter((r) => r.trim());
  if (rules.length) {
    lines.push("硬规则：");
    rules.forEach((r) => lines.push(`- ${r.replace(/^-\s*/, "")}`));
  }
  return lines.join("\n");
}

async function savePersona(payload) {
  const current = personaData();
  const body = {
    prompt: payload.prompt !== undefined ? payload.prompt : current.prompt,
    modes: { ...current.modes, ...(payload.modes || {}) },
  };
  await api("/persona", { method: "PUT", body: JSON.stringify(body) });
  state.data.persona = await api("/persona");
  renderPersona();
}

function renderPersona() {
  const pane = $("#pane-persona");
  pane.replaceChildren();
  const data = personaData();

  const global = card("全局系统提示词", "所有身份与模式都会注入");
  const prompt = document.createElement("textarea");
  prompt.value = data.prompt;
  prompt.placeholder = "例如：你在帮用户处理工作事务，回答先给结论，不编造事实。";
  prompt.rows = 6;
  global.append(prompt);
  const actions = el("div", "actions");
  const save = el("button", "primary", "保存全局");
  save.addEventListener("click", () => savePersona({ prompt: prompt.value }));
  actions.append(save);
  global.append(actions);
  pane.append(global);

  const seg = el("div", "seg");
  seg.style.marginTop = "2px";
  for (const mode of MODES) {
    const b = el("button", state.personaMode === mode.id ? "on" : "", mode.label);
    b.addEventListener("click", () => { state.personaMode = mode.id; renderPersona(); });
    seg.append(b);
  }
  const modeCard = card("按模式追加", "留空则只用全局");
  modeCard.append(seg);

  const cfg = data.modes[state.personaMode] || {};
  const form = el("div");
  const mk = (label, key, placeholder, multiline) => {
    const wrap = el("label", "field");
    wrap.append(el("span", "", label));
    const input = document.createElement(multiline ? "textarea" : "input");
    input.value = cfg[key] || "";
    input.placeholder = placeholder;
    input.dataset.key = key;
    if (multiline) input.rows = 3;
    wrap.append(input);
    form.append(wrap);
  };
  mk("身份", "identity", "例如：用户的工作助理", false);
  mk("说话风格", "tone", "例如：简短直接，先给结论", true);
  mk("硬规则（每行一条）", "rules", "不编造事实\n改动文件前先说明", true);

  const modeActions = el("div", "actions");
  const saveMode = el("button", "primary", "保存模式");
  saveMode.addEventListener("click", () => {
    const payload = {};
    form.querySelectorAll("[data-key]").forEach((node) => { payload[node.dataset.key] = node.value; });
    savePersona({ modes: { [state.personaMode]: payload } });
  });
  modeActions.append(saveMode);
  form.append(modeActions);
  modeCard.append(form);
  pane.append(modeCard);

  const preview = card("实际注入", "append 到会话");
  const composed = [data.prompt.trim(), modeBlock(state.personaMode)].filter(Boolean).join("\n\n");
  const pre = el("div", "mono");
  pre.style.whiteSpace = "pre-wrap";
  pre.textContent = composed || "（未配置）";
  preview.append(pre);
  pane.append(preview);
}

/* ---------------------------------------------------------------- 人物 */
function renderPeople(data) {
  const pane = $("#pane-people");
  pane.replaceChildren();
  const box = card("人物卡片", `${(data.items || []).length} 人`);
  const items = data.items || [];
  if (!items.length) box.append(empty("还没有记录"));
  for (const person of items) {
    const line = el("div", "item");
    line.append(el("div", "t", person.name || "(未命名)"));
    const meta = el("div", "m");
    meta.append(chip(person.relation || "朋友", ""), " ");
    if (person.alias) meta.append(el("span", "", `别名 ${person.alias} `));
    if (person.note) meta.append(el("span", "", person.note));
    line.append(meta);
    const del = el("button", "ghost", "删除");
    del.style.marginTop = "4px";
    del.addEventListener("click", async () => {
      await api(`/persons/${person.id}`, { method: "DELETE" });
      loadPeople();
    });
    line.append(del);
    box.append(line);
  }
  pane.append(box);

  const add = card("添加");
  const form = el("div");
  const fields = {};
  for (const [key, label, placeholder] of [
    ["name", "名字", "对方的名字"],
    ["alias", "别名", "可选"],
    ["relation", "关系", "同事 / 朋友"],
    ["note", "备注", "可选"],
  ]) {
    const wrap = el("label", "field");
    wrap.append(el("span", "", label));
    const input = el("input");
    input.placeholder = placeholder;
    fields[key] = input;
    wrap.append(input);
    form.append(wrap);
  }
  const actions = el("div", "actions");
  const submit = el("button", "primary", "添加");
  submit.addEventListener("click", async () => {
    if (!fields.name.value.trim()) return;
    await api("/persons", { method: "POST", body: JSON.stringify({
      name: fields.name.value, alias: fields.alias.value,
      relation: fields.relation.value || "朋友", note: fields.note.value,
    })});
    loadPeople();
  });
  actions.append(submit);
  form.append(actions);
  add.append(form);
  pane.append(add);
}

/* ---------------------------------------------------------------- 配置 */
const cfgState = { identityMode: null };

async function saveConfig(patch, note) {
  const result = await api("/config", { method: "PUT", body: JSON.stringify(patch) });
  state.data.config = await api("/config");
  renderConfig(state.data.config);
  if (note) {
    const toast = el("div", "empty", result.restart_required ? "已保存，重载插件后生效" : "已保存");
    $("#pane-config").prepend(toast);
    setTimeout(() => toast.remove(), 2500);
  }
}

function modeSelect(value, options, onChange) {
  const select = document.createElement("select");
  select.className = "mini";
  for (const [key, label] of options) {
    const option = el("option", "", label);
    option.value = key;
    if (value === key) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () => onChange(select.value));
  return select;
}

function recentWorkspaces() {
  try { return JSON.parse(localStorage.getItem("sugar.workspaces") || "[]"); } catch (_) { return []; }
}

function rememberWorkspace(path) {
  if (!path) return;
  const list = recentWorkspaces().filter((item) => item !== path);
  list.unshift(path);
  localStorage.setItem("sugar.workspaces", JSON.stringify(list.slice(0, 6)));
}

function renderConfig(config) {
  const pane = $("#pane-config");
  pane.replaceChildren();
  const identity = config.identity || { mode: "bot", chats: [] };
  const defaults = config.defaults || {};
  const ws = defaults.workspace || { mode: "host", path: "" };
  const identityMode = cfgState.identityMode || identity.mode || "bot";

  const base = card("会话默认工作目录", "新建会话时使用");

  // 默认工作目录
  const wsBlock = el("div", "fieldblock");
  const wsRow = el("div", "pathrow");
  const wsInput = document.createElement("input");
  wsInput.value = ws.mode === "manual" ? (ws.path || "") : "";
  wsInput.placeholder = "留空则使用宿主工作区";
  const wsBrowse = el("button", "iconbtn");
  wsBrowse.title = "选择文件夹";
  wsBrowse.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/></svg>';
  wsBrowse.addEventListener("click", async () => {
    wsBrowse.disabled = true;
    try {
      const res = await fetch("/api/pick-path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ kind: "directory", initial: wsInput.value.trim() || config.host_workspace || "" }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.ok && data.path) {
        wsInput.value = data.path;
        rememberWorkspace(data.path);
      } else if (!data.cancelled) {
        window.alert(data.error || "无法打开选择对话框");
      }
    } catch (err) {
      window.alert(`无法打开选择对话框：${err.message}`);
    } finally {
      wsBrowse.disabled = false;
    }
  });
  wsRow.append(wsInput, wsBrowse);
  wsBlock.append(wsRow);
  base.append(wsBlock);

  const actions = el("div", "actions");
  const save = el("button", "primary", "保存");
  save.addEventListener("click", () => {
    saveConfig({
      session_scope: "chat",
      defaults: {
        workspace: wsInput.value.trim()
          ? { mode: "manual", path: wsInput.value.trim() }
          : { mode: "host", path: "" },
      },
    }, true);
  });
  actions.append(save);
  base.append(actions);
  pane.append(base);

  // 发送身份
  const who = card("发送身份", "切换后重载插件");
  const whoHead = el("div", "fieldhead");
  whoHead.append(el("span", "", "发送身份"));
  whoHead.append(modeSelect(identityMode, [["bot", "机器人"], ["user", "我的账号"]],
    (value) => { cfgState.identityMode = value; renderConfig(state.data.config); }));
  who.append(whoHead);
  const chatsWrap = el("label", "field");
  chatsWrap.append(el("span", "", "user 模式轮询的会话（每行一个 chat_id）"));
  const chats = document.createElement("textarea");
  chats.rows = 3;
  chats.value = (identity.chats || []).join("\n");
  chats.disabled = identityMode !== "user";
  chats.placeholder = "oc_xxx\noc_yyy";
  chatsWrap.append(chats);
  who.append(chatsWrap);
  const whoActions = el("div", "actions");
  const saveWho = el("button", "primary", "保存身份");
  saveWho.addEventListener("click", () => saveConfig({ identity: { mode: identityMode, chats: chats.value } }, true));
  whoActions.append(saveWho);
  who.append(whoActions);
  pane.append(who);

  for (const [name, cfg] of Object.entries(config.channels || {})) {
    const box = card(`通道 · ${name}`);
    const toggleRow = el("div", "row");
    toggleRow.append(el("span", "k", "启用"));
    const toggle = document.createElement("input");
    toggle.type = "checkbox"; toggle.checked = !!cfg.enabled; toggle.style.width = "auto";
    toggleRow.append(toggle);
    box.append(toggleRow);

    const quotaBlock = el("div", "fieldblock");
    const quotaHead = el("div", "fieldhead");
    quotaHead.append(el("span", "", "配额"));
    const quota = modeSelect(cfg.quota || "none",
      [["none", "不限"], ["rate", "按频率"], ["window10", "10 条窗口"]], () => {});
    quotaHead.append(quota);
    quotaBlock.append(quotaHead);
    box.append(quotaBlock);

    const allowField = el("label", "field");
    allowField.append(el("span", "", "允许的人（白名单，逗号分隔）"));
    const allow = document.createElement("textarea");
    allow.rows = 2;
    allow.value = (cfg.allow || []).join(", ");
    allow.placeholder = "ou_xxx, feishu:ou_yyy";
    allowField.append(allow);
    box.append(allowField);

    const groupField = el("label", "field");
    groupField.append(el("span", "", "允许的群（按私聊档，逗号分隔）"));
    const groups = document.createElement("textarea");
    groups.rows = 2;
    groups.value = (cfg.allow_groups || []).join(", ");
    groupField.append(groups);
    box.append(groupField);

    const channelActions = el("div", "actions");
    const saveChannel = el("button", "primary", "保存通道");
    saveChannel.addEventListener("click", () => saveConfig({
      channels: { [name]: { enabled: toggle.checked, quota: quota.value, allow: allow.value, allow_groups: groups.value } },
    }, true));
    channelActions.append(saveChannel);
    box.append(channelActions);
    pane.append(box);
  }

  const web = config.web || {};
  const webBox = card("浏览器兜底", "跨租户私聊唯一可用");
  const webRow = el("div", "row");
  webRow.append(el("span", "k", "启用"));
  const webOn = document.createElement("input");
  webOn.type = "checkbox"; webOn.checked = !!web.enabled; webOn.style.width = "auto";
  webRow.append(webOn);
  webBox.append(webRow);
  const tenantField = el("label", "field");
  tenantField.append(el("span", "", "租户域名（如 xxx.feishu.cn）"));
  const tenantInput = document.createElement("input");
  tenantInput.value = web.tenant || "";
  tenantInput.placeholder = "acneut3zrdux.feishu.cn";
  tenantField.append(tenantInput);
  webBox.append(tenantField);
  const cdpField = el("label", "field");
  cdpField.append(el("span", "", "CDP 地址（可选，接管已登录 Edge）"));
  const cdpInput = document.createElement("input");
  cdpInput.value = web.cdp_url || "";
  cdpInput.placeholder = "http://127.0.0.1:9222";
  cdpField.append(cdpInput);
  webBox.append(cdpField);
  const webState = el("div", "m");
  webState.textContent = web.available ? "登录态可用" : (web.reason || "未启用");
  webBox.append(webState);
  const webActions = el("div", "actions");
  const loginBtn = el("button", "", "扫码登录");
  loginBtn.addEventListener("click", async () => {
    await api("/web/login", { method: "POST", body: "{}" });
    state.data.config = await api("/config");
    renderConfig(state.data.config);
  });
  const saveWeb = el("button", "primary", "保存浏览器通道");
  saveWeb.addEventListener("click", async () => {
    await api("/web", { method: "PUT", body: JSON.stringify({
      enabled: webOn.checked, tenant: tenantInput.value.trim(),
      cdp_url: cdpInput.value.trim(), headless: web.headless !== false }) });
    state.data.config = await api("/config");
    renderConfig(state.data.config);
  });
  webActions.append(loginBtn, saveWeb);
  webBox.append(webActions);
  pane.append(webBox);

  const note = card("需要环境变量的项", "改后需重启");
  const text = el("div", "m");
  text.textContent = "合并窗口 SUGAR_MERGE_MS、快速回执 SUGAR_ACK、群聊审批接收人 SUGAR_OWNER_CHAT_ID 只能通过环境变量配置。";
  note.append(text);
  pane.append(note);
}

function modelLabelAppend(block, control) {
  block.append(control);
}

/* ---------------------------------------------------------------- 日志 */
function renderLogs(data) {
  const pane = $("#pane-logs");
  pane.replaceChildren();
  const box = card("最近事件", "最多 100 条");
  const items = data.items || [];
  if (!items.length) box.append(empty("暂无日志"));
  for (const item of items.slice(0, 100)) {
    const line = el("div", "logline");
    const ts = new Date((item.ts || 0) * 1000).toLocaleTimeString("zh-CN", { hour12: false });
    line.append(el("span", "ts", ts), el("span", "kind", item.kind || "?"));
    const rest = Object.entries(item).filter(([k]) => !["ts", "kind"].includes(k))
      .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ");
    line.append(el("span", "", rest.slice(0, 160)));
    box.append(line);
  }
  pane.append(box);
}

/* ---------------------------------------------------------------- 加载 */
async function loadStatus() {
  const status = await api("/status");
  state.data.status = status;
  state.data.persona = status.persona;
  $("#subline").textContent = status.core
    ? `${status.channels.filter((c) => c.running).length}/${status.channels.length} 通道在线 · ${status.conversations} 会话`
    : "Core 未运行";
  const dot = $("#healthDot");
  dot.className = "dot " + (!status.core ? "bad" : status.channels.some((c) => c.enabled && !c.running) ? "warn" : "ok");
  renderOverview(status);
  renderPersona();
}

async function loadChats() {
  const data = await api("/conversations");
  state.data.chats = data;
  renderChats(data);
}

async function loadPeople() {
  const data = await api("/persons");
  state.data.people = data;
  renderPeople(data);
}

async function loadConfig() {
  const data = await api("/config");
  state.data.config = data;
  renderConfig(data);
}

async function loadLogs() {
  const data = await api("/logs?limit=100");
  state.data.logs = data;
  renderLogs(data);
}

const loaders = { overview: loadStatus, chats: loadChats, persona: loadStatus, people: loadPeople, config: loadConfig, logs: loadLogs };

async function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.id === `pane-${name}`));
  try { await loaders[name](); } catch (err) {
    const pane = $(`#pane-${name}`);
    pane.replaceChildren(empty(`读取失败：${err.message}`));
  }
}

$("#tabs").addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-tab]");
  if (btn) showTab(btn.dataset.tab);
});
$("#refresh").addEventListener("click", () => {
  const active = $(".tabs button.on");
  showTab(active ? active.dataset.tab : "overview");
});

showTab("overview");
let statusPolling = false;
setInterval(async () => {
  if (statusPolling || !$("#pane-overview").classList.contains("on")) return;
  statusPolling = true;
  try {
    await loadStatus();
  } catch (err) {
    /* keep the next tick quiet; the tab shows the failure on manual refresh */
  } finally {
    statusPolling = false;
  }
}, 15000);
