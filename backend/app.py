from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.orchestrator import get_crawl_job, start_crawl_job


app = FastAPI(title="Onion Network Crawler API", version="0.1.0")

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
def crawl_start() -> dict:
    job = start_crawl_job()
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
