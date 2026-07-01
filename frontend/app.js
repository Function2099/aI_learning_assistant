const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const apiUrlEl = document.getElementById("api-url");

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

// 移除歡迎畫面
function clearWelcome() {
  const welcome = chatEl.querySelector(".welcome");
  if (welcome) welcome.remove();
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

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message) return;

  const baseUrl = (apiUrlEl.value.trim() || window.location.origin).replace(
    /\/+$/,
    ""
  );

  addMessage("user", message);
  inputEl.value = "";
  autoGrow();
  setBusy(true);
  showTyping();

  try {
    const res = await fetch(`${baseUrl}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    removeTyping();

    if (!res.ok) {
      addMessage("assistant", `⚠️ 後端錯誤（${res.status}）：${await res.text()}`);
      return;
    }

    // 先建一個空泡泡，之後逐字填入
    const bubble = addMessage("assistant", "");
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
          fullText += JSON.parse(data);
          // 用 marked 把 markdown 渲染成 HTML，跟原本一樣
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
  }finally {
    setBusy(false);
    inputEl.focus();
  }
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  inputEl.disabled = busy;
}
