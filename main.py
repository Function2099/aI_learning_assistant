import os
import re
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# 讀取.env環境變數
load_dotenv()
app = FastAPI(title="AI 學習助手", version="0.2.0")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

# 系統提示詞 : 先放基礎版本
SYSTEM_PROMPT = """
你是一個AI工程師學習駐守，你是一個 AI 工程師學習助手，協助使用者學習 AI 開發。

使用者背景：
- Java 後端工程師 (有Spring boot 經驗)
- 會 Python 基礎、JavaScript
- 正在學習 AI 工程師轉職路徑

請用簡潔、實用的風格，並使用繁體中文回答。禁止使用大陸用語、簡體字、表情符號。
遇到適合的情境可以用 Java/Spring Boot 類比解釋 Python 或 AI 的概念。
"""

# 定義請求的資料格式(DTO)
class ChatRequest(BaseModel):
    message: str

# 定義回應的資料格式
class ChatResponse(BaseModel):
    reply: str

@app.get("/")
def root():
    return {"status":"ok", "message": "AI 學習助手啟動中"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # 呼叫 Groq API ，啟用 LLM 回答問題
    completion = client.chat.completions.create(
        model="qwen/qwen3-32b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message},
        ],
    )

    reply = completion.choices[0].message.content
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
    return ChatResponse(reply=reply)