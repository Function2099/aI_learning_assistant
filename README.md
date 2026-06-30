# AI 開發學習助手

用 FastAPI + Groq 打造的個人 AI 導師，針對 Java 工程師轉 AI 工程師的學習路徑設計。

## 目前進度

- [x] Day 1：FastAPI 基礎端點
- [x] Day 2：串接 Groq LLM API
- [ ] Day 3：System Prompt 設定
- [ ] Day 4：Streaming SSE
- [x] Day 5：前端介面（ChatGPT 風格聊天 UI）

## 快速啟動

FastAPI 同時提供前端靜態檔案與 API，只需啟動一個伺服器。

```bash
# 安裝 uv（第一次）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 建立虛擬環境 + 安裝依賴
uv sync

# 啟動伺服器
uv run uvicorn main:app --reload
```

啟動後瀏覽器開啟：http://localhost:8000

- 聊天介面：`/`
- API 文件：`/docs`
- 健康檢查：`/health`

## 技術架構

```
使用者
  │
  ▼
FastAPI (Python)     ← API + 前端靜態檔案
  │
  ▼
Groq API
(qwen/qwen3-32b)
```

## 測試 API

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "RAG 是什麼？"}'
```