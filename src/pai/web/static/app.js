const messagesEl = document.getElementById("messages");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send");
const statusEl = document.getElementById("status");
const providerEl = document.getElementById("provider");
const modelEl = document.getElementById("model");
const sessionEl = document.getElementById("sessionId");
const noticesEl = document.getElementById("notices");
const streamToggle = document.getElementById("streamToggle");
const newChatBtn = document.getElementById("newChat");

let sessionId = null;
let streamDefault = false;

function setStatus(text) {
  statusEl.textContent = text;
}

function addMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;
  msg.textContent = text;
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return msg;
}

function updateMessage(el, text) {
  el.textContent = text;
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderNotices(notices) {
  if (!notices || notices.length === 0) {
    noticesEl.textContent = "None";
    return;
  }
  noticesEl.innerHTML = "";
  notices.forEach((n) => {
    const item = document.createElement("div");
    if (typeof n === "string") {
      item.textContent = n;
    } else {
      const dropped = n.dropped ? Object.keys(n.dropped).join(", ") : "";
      item.textContent = `[${n.provider}] ${n.message || "Policy notice"} ${dropped ? `(${dropped})` : ""}`;
    }
    noticesEl.appendChild(item);
  });
}

async function fetchConfig() {
  const res = await fetch("/api/config");
  const cfg = await res.json();
  providerEl.textContent = cfg.provider || "—";
  modelEl.textContent = cfg.model || "—";
  streamDefault = Boolean(cfg.stream);
  streamToggle.checked = streamDefault;
  renderNotices(cfg.warnings || []);
}

async function newSession() {
  const res = await fetch("/api/session", { method: "POST" });
  const data = await res.json();
  sessionId = data.session_id;
  sessionEl.textContent = sessionId || "—";
  messagesEl.innerHTML = "";
  setStatus("Ready");
}

async function sendMessage() {
  const text = promptEl.value.trim();
  if (!text) return;
  promptEl.value = "";
  addMessage("user", text);
  setStatus("Thinking…");

  const useStream = streamToggle.checked;
  if (!useStream) {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });
    const data = await res.json();
    sessionId = data.session_id;
    sessionEl.textContent = sessionId || "—";
    addMessage("assistant", data.reply || "");
    setStatus("Ready");
    return;
  }

  const assistantEl = addMessage("assistant", "");
  const res = await fetch("/api/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message: text }),
  });
  const headerId = res.headers.get("X-Session-Id");
  if (headerId) {
    sessionId = headerId;
    sessionEl.textContent = sessionId;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    updateMessage(assistantEl, buffer);
  }
  setStatus("Ready");
}

promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);
newChatBtn.addEventListener("click", newSession);

async function init() {
  await fetchConfig();
  await newSession();
}

init();
