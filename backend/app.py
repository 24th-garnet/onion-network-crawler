from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.orchestrator import get_crawl_job, start_crawl_job


app = FastAPI(title="Onion Network Crawler API", version="0.1.0")


class StartRequest(BaseModel):
    maxDepth: int = Field(default=1, ge=0, le=5)

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
    job = start_crawl_job(max_depth=payload.maxDepth)
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
    return {"ok": True, "job": job.to_dict()}
