# src/api.py
"""FastAPI. Gira SUL POD, accanto a llama-server."""

import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import db
from src.llm.client import LlamaCppClient
from src.pipeline import processa

LLAMA_URL = "http://127.0.0.1:8080"   # stesso host: niente rete di mezzo

app = FastAPI(title="DocRouter")
client = LlamaCppClient(LLAMA_URL)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


class ProcessRequest(BaseModel):
    testo: str
    doc_id: str | None = None


@app.post("/api/process")
def api_process(req: ProcessRequest) -> dict:
    t0 = time.perf_counter()
    doc = processa(req.testo, client, doc_id=req.doc_id)
    latency = int((time.perf_counter() - t0) * 1000)
    db.salva(doc, latency_ms=latency)
    return {**doc.model_dump(), "latency_ms": latency}


@app.get("/api/documents")
def api_documents(
    routing: str | None = None,
    campo: str | None = None,
    q: str | None = None,
    solo_scartati: bool = False,
    limit: int = 100,
) -> list[dict]:
    return db.cerca(routing=routing, campo=campo, q=q,
                    solo_scartati=solo_scartati, limit=limit)


@app.get("/api/documents/{doc_id}")
def api_document(doc_id: str) -> dict:
    d = db.leggi(doc_id)
    if d is None:
        raise HTTPException(404, "documento non trovato")
    return d


@app.get("/api/stats")
def api_stats() -> dict:
    return db.stats()


@app.get("/api/telemetry")
def api_telemetry() -> dict:
    """GPU + metriche llama.cpp. È il pannello che rende visibile
    che questo NON è ChatGPT."""
    import subprocess

    gpu: dict = {}
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        name, used, total, util, temp = [x.strip() for x in out.split(",")]
        gpu = {
            "name": name,
            "vram_used_mb": int(used),
            "vram_total_mb": int(total),
            "util_pct": int(util),
            "temp_c": int(temp),
        }
    except Exception as e:
        gpu = {"error": str(e)}

    llama: dict = {}
    try:
        r = httpx.get(f"{LLAMA_URL}/metrics", timeout=2)
        for riga in r.text.splitlines():
            if riga.startswith("#") or " " not in riga:
                continue
            k, v = riga.rsplit(" ", 1)
            if k.startswith("llamacpp:"):
                llama[k.replace("llamacpp:", "")] = float(v)
    except Exception as e:
        llama = {"error": str(e)}

    return {"gpu": gpu, "llama": llama}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")