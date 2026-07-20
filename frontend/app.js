const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const apiUrlEl = document.getElementById("api-url");
const clearChatBtn = document.getElementById("clear-chat");
const sidebarEl = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebar-toggle");
const sidebarToggleTopEl = document.getElementById("sidebar-toggle-top");
const appEl = document.querySelector(".app");

const SIDEBAR_COLLAPSED_KEY = "sidebar-collapsed";

const temperatureEl = document.getElementById("temperature");
const temperatureValueEl = document.getElementById("temperature-value");
const maxTokensEl = document.getElementById("max-tokens");
const maxHistoryTurnsEl = document.getElementById("max-history-turns");
const maxHistoryTurnsValueEl = document.getElementById("max-history-turns-value");
const topPEl = document.getElementById("top-p");
const topPValueEl = document.getElementById("top-p-value");

const DEFAULT_SETTINGS = {
  temperature: 1.0,
  max_tokens: 1024,
  max_history_turns: 5,
  top_p: 1.0,
};
const SETTINGS_KEY = "chat-settings";

const WELCOME_HTML = `
  <div class="welcome">
    <div class="welcome-emoji">🧭</div>
    <h2>開始測試你的提示詞</h2>
    <p>直接在下方輸入問題，回覆會以聊天泡泡呈現，比 /docs 直觀多了。</p>
  </div>
`;

// 記住上次使用的後端位址（留空則使用同源）
const SAVED_URL = localStorage.getItem("api-url");
if (SAVED_URL) apiUrlEl.value = SAVED_URL;
apiUrlEl.addEventListener("change", () => {
  const url = apiUrlEl.value.trim();
  if (url) {
    localStorage.setItem("api-url", url);
  } else {
    localStorage.removeItem("api-url");
  }
});

function loadSettings() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
  } catch {}
  return { ...DEFAULT_SETTINGS, ...saved };
}

function getSettings() {
  return {
    temperature: parseFloat(temperatureEl.value),
    max_tokens: parseInt(maxTokensEl.value, 10),
    max_history_turns: parseInt(maxHistoryTurnsEl.value, 10),
    top_p: parseFloat(topPEl.value),
  };
}

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(getSettings()));
}

function applySettingsToUI(settings) {
  temperatureEl.value = settings.temperature;
  temperatureValueEl.textContent = settings.temperature.toFixed(1);
  maxTokensEl.value = settings.max_tokens;
  maxHistoryTurnsEl.value = settings.max_history_turns;
  maxHistoryTurnsValueEl.textContent = String(settings.max_history_turns);
  topPEl.value = settings.top_p;
  topPValueEl.textContent = settings.top_p.toFixed(1);
}

applySettingsToUI(loadSettings());

function setSidebarCollapsed(collapsed) {
  sidebarEl.classList.toggle("collapsed", collapsed);
  appEl.classList.toggle("sidebar-collapsed", collapsed);
  const expanded = !collapsed;
  sidebarToggleEl.setAttribute("aria-expanded", String(expanded));
  sidebarToggleEl.setAttribute("aria-label", expanded ? "收合設定" : "展開設定");
  sidebarToggleTopEl.setAttribute("aria-expanded", String(expanded));
  sidebarToggleTopEl.setAttribute("aria-label", expanded ? "收合設定" : "開啟設定");
  localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
}

function toggleSidebar() {
  setSidebarCollapsed(!sidebarEl.classList.contains("collapsed"));
}

if (localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1") {
  setSidebarCollapsed(true);
}

sidebarToggleEl.addEventListener("click", toggleSidebar);
sidebarToggleTopEl.addEventListener("click", toggleSidebar);

temperatureEl.addEventListener("input", () => {
  temperatureValueEl.textContent = parseFloat(temperatureEl.value).toFixed(1);
  saveSettings();
});

maxHistoryTurnsEl.addEventListener("input", () => {
  maxHistoryTurnsValueEl.textContent = maxHistoryTurnsEl.value;
  saveSettings();
});

topPEl.addEventListener("input", () => {
  topPValueEl.textContent = parseFloat(topPEl.value).toFixed(1);
  saveSettings();
});

let lastValidMaxTokens = loadSettings().max_tokens;
maxTokensEl.addEventListener("change", () => {
  const val = parseInt(maxTokensEl.value, 10);
  if (Number.isNaN(val) || val < 1 || val > 8192) {
    maxTokensEl.value = lastValidMaxTokens;
    return;
  }
  lastValidMaxTokens = val;
  saveSettings();
});

// 輸入框：自動長高
function autoGrow() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 180) + "px";
}
inputEl.addEventListener("input", autoGrow);

// Enter 送出，Shift + Enter 換行
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
sendBtn.addEventListener("click", sendMessage);
clearChatBtn.addEventListener("click", clearChat);

function getBaseUrl() {
  return (apiUrlEl.value.trim() || window.location.origin).replace(/\/+$/, "");
}

// 移除歡迎畫面
function clearWelcome() {
  const welcome = chatEl.querySelector(".welcome");
  if (welcome) welcome.remove();
}

function resetChatUI() {
  chatEl.innerHTML = WELCOME_HTML;
}

// 加入一則訊息泡泡，回傳該泡泡的內容元素
function addMessage(role, text, isHtml = false) {
  clearWelcome();
  const row = document.createElement("div");
  row.className = `row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (isHtml) {
    bubble.innerHTML = text;
  } else {
    bubble.textContent = text;
  }
  row.appendChild(bubble);
  chatEl.appendChild(row);
  scrollToBottom();
  return bubble;
}

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function appendProgressHint(row, progressUpdated, pendingConfirmation, progressRemoved, pendingAction) {
  if (progressUpdated?.length) {
    const hint = document.createElement("p");
    hint.className = "progress-hint progress-hint-updated";
    hint.textContent = `進度已更新：${progressUpdated.join("、")}`;
    row.appendChild(hint);
  }
  if (progressRemoved?.length) {
    const hint = document.createElement("p");
    hint.className = "progress-hint progress-hint-removed";
    hint.textContent = `進度已移除：${progressRemoved.join("、")}`;
    row.appendChild(hint);
  }
  if (pendingConfirmation?.length) {
    const hint = document.createElement("p");
    hint.className = "progress-hint progress-hint-pending";
    const actionText =
      pendingAction === "remove"
        ? "待確認移除"
        : "待確認";
    hint.textContent = `${actionText}：${pendingConfirmation.join("、")}（回覆「確認」以寫入）`;
    row.appendChild(hint);
  }
}

function showTyping() {
  clearWelcome();
  const row = document.createElement("div");
  row.className = "row assistant";
  row.id = "typing-row";
  row.innerHTML = `<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  chatEl.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  const t = document.getElementById("typing-row");
  if (t) t.remove();
}

let currentSessionId = "";

async function clearChat() {
  const baseUrl = getBaseUrl();

  if (currentSessionId) {
    try {
      await fetch(`${baseUrl}/session/${currentSessionId}`, { method: "DELETE" });
    } catch {}
  }

  currentSessionId = "";
  resetChatUI();
  inputEl.focus();
}

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message) return;

  const baseUrl = getBaseUrl();

  addMessage("user", message);
  inputEl.value = "";
  autoGrow();
  setBusy(true);
  showTyping();

  try {
    const res = await fetch(`${baseUrl}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: currentSessionId,
        settings: getSettings(),
      }),
    });

    removeTyping();

    if (!res.ok) {
      addMessage("assistant", `⚠️ 後端錯誤（${res.status}）：${await res.text()}`);
      return;
    }

    // 先建一個空泡泡，之後逐字填入
    const bubble = addMessage("assistant", "");
    const bubbleRow = bubble.closest(".row");
    let fullText = "";

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const lines = decoder.decode(value).split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") break;

        try {
          const parsed = JSON.parse(data);
          if (parsed && typeof parsed === "object") {
            if (parsed.error) {
              bubble.textContent = `⚠️ ${parsed.error}`;
              break;
            }
            if (parsed.done) {
              currentSessionId = parsed.session_id;
              appendProgressHint(
                bubbleRow,
                parsed.progress_updated,
                parsed.pending_confirmation,
                parsed.progress_removed,
                parsed.pending_action
              );
              scrollToBottom();
              break;
            }
          }
          fullText += parsed;
          bubble.innerHTML = marked.parse(fullText);
          scrollToBottom();
        } catch {}
      }
    }
  } catch (err) {
    removeTyping();
    addMessage(
      "assistant",
      `⚠️ 連線失敗：請確認後端已啟動，且位址正確（目前：${baseUrl}）。\n\n${err.message}`
    );
  } finally {
    setBusy(false);
    inputEl.focus();
  }
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  inputEl.disabled = busy;
  clearChatBtn.disabled = busy;
}
