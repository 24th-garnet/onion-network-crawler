from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.orchestrator import get_crawl_job, start_crawl_job


app = FastAPI(title="Onion Network Crawler API", version="0.1.0")


class StartRequest(BaseModel):
    maxDepth: int = Field(default=1, ge=0, le=5)
    seedText: str = ""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true", "status": "healthy"}


@app.post("/crawl/start")
def crawl_start(payload: StartRequest) -> dict:
    job = start_crawl_job(max_depth=payload.maxDepth, seed_text=payload.seedText)
    return {
        "ok": True,
        "job": {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
        },
    }


@app.get("/crawl/status")
def crawl_status() -> dict:
    job = get_crawl_job()
    if job is None:
        return {"ok": True, "job": None}
    payload = job.to_dict()
    # Avoid multi‑MB JSON on every poll; HTML is served by GET /crawl/result
    has_viz = bool(payload.get("visualizationHtml"))
    payload.pop("visualizationHtml", None)
    payload["hasVisualization"] = has_viz
    return {"ok": True, "job": payload}


@app.get("/crawl/result", response_class=HTMLResponse)
def crawl_result() -> HTMLResponse:
    job = get_crawl_job()
    if job is None or job.status != "done":
        raise HTTPException(status_code=404, detail="No completed crawl job")
    html = job.visualizationHtml
    if not html:
        raise HTTPException(status_code=404, detail="No visualization HTML available")
    return HTMLResponse(content=html)
