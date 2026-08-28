from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import json
import asyncio

from .agent.engine import run_agent_pipeline
from .services.cache_service import cache_service
from .services.report_storage import (
    save_markdown_report,
    list_all_reports,
    get_report_content,
    delete_report_file,
    REPORTS_DIR
)
import os

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

class SaveReportRequest(BaseModel):
    symbol: str
    content: str
    meta: dict = {}

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

# --- 📂 리포트 보관함 API ---
@app.get("/api/reports")
def get_reports():
    reports = list_all_reports()
    return {"reports": reports, "total": len(reports)}

@app.post("/api/reports")
def create_report(req: SaveReportRequest):
    try:
        saved_meta = save_markdown_report(req.symbol, req.content, req.meta)
        return {"status": "success", "report": saved_meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports/{filename}")
def read_report(filename: str):
    res = get_report_content(filename)
    if not res:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    return res

@app.delete("/api/reports/{filename}")
def remove_report(filename: str):
    success = delete_report_file(filename)
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 리포트가 존재하지 않습니다.")
    return {"status": "success", "message": f"{filename} 삭제 완료"}

@app.get("/api/reports/{filename}/download")
def download_report(filename: str):
    safe_name = os.path.basename(filename)
    file_path = os.path.join(REPORTS_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path, filename=safe_name, media_type="text/markdown")

from .tools.market_data import KNOWN_TICKERS

@app.get("/api/stocks/search")
def search_stocks(q: str = ""):
    query = q.strip().lower()
    if not query:
        return []
    results = []
    seen = set()
    for name, code in KNOWN_TICKERS.items():
        if query in name.lower() or query in str(code):
            if code not in seen:
                seen.add(code)
                results.append({"name": name, "code": code})
                if len(results) >= 15:
                    break
    return results

@app.post("/api/cache/clear")
def clear_cache():
    cache_service.clear()
    return {"status": "success", "message": "캐시가 초기화되었습니다."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
