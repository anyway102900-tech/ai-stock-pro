from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio

from .agent.engine import run_agent_pipeline
from .services.cache_service import cache_service

app = FastAPI(title="AI Stock Fact-Check Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    prompt: str
    force_refresh: bool = False

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "AI Stock Fact-Check Agent is running"}

@app.post("/api/analyze")
async def analyze_stock(req: AnalyzeRequest):
    async def event_generator():
        async for event in run_agent_pipeline(req.prompt, req.force_refresh):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/cache/clear")
def clear_cache():
    cache_service.clear()
    return {"status": "success", "message": "캐시가 초기화되었습니다."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
