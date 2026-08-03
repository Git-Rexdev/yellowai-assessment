import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agent import TrendlyAgent
from app.data import get_all_customers

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
PORT = int(os.getenv("PORT", "8000"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

agent: TrendlyAgent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    if not API_KEY:
        logger.warning("GROQ_API_KEY is not set. Chat will fail. Create a .env file with your key (see .env.example).")
    agent = TrendlyAgent(api_key=API_KEY, model=MODEL_NAME)
    logger.info(f"Trendly Agent started with model={MODEL_NAME}")
    yield
    logger.info("Trendly Agent shutting down")


app = FastAPI(title="Trendly Support Agent", description="AI-powered customer support for Trendly fashion retail", version="1.0.0", lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ChatRequest(BaseModel):
    session_id: str
    customer_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    escalated: bool


@app.get("/")
async def serve_ui():
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        return {"message": "Trendly Support Agent API is running. No UI found at /static/index.html."}
    return FileResponse(index_path)


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "model": MODEL_NAME, "api_key_set": bool(API_KEY)}


@app.get("/api/customers")
async def list_customers():
    return get_all_customers()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    if not API_KEY:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured. Please set it in your .env file.")
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if not request.customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    logger.info(f"Chat request: session={request.session_id[:8]}... customer={request.customer_id} message={request.message[:50]}...")

    try:
        result = agent.chat(session_id=request.session_id, customer_id=request.customer_id, user_message=request.message)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")

    if result.get("tool_calls"):
        for tc in result["tool_calls"]:
            logger.info(f"  Tool: {tc['name']}({tc['arguments']})")

    return ChatResponse(response=result["response"], escalated=result["escalated"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True, log_level="info")
