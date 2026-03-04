"""
api/main.py  ·  Orchestra-Agent  ·  FastAPI Backend
=====================================================
WHY FastAPI as a separate process?
  - Separates AI/CPU work from the Streamlit UI process
  - Enables horizontal scaling (multiple Streamlit instances,
    one shared API backend)
  - /health endpoint lets Docker/uptime monitors verify liveness
    without importing the full LangGraph stack

Memory budget on 8 GB machine:
  FastAPI (uvicorn)  ~80 MB
  LangGraph + model  ~200-600 MB (depends on LLM backend)
  Streamlit          ~120 MB
  SQLite             negligible
  OS + buffer        ~1 GB
  ─────────────────────────
  Safe headroom remains for Docker overhead and OS swap.
"""

import os
import sys
import time
import psutil
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# ── Make sure sibling modules are importable ──────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import init_db, get_db_stats

# ── Loguru configuration ──────────────────────────────────────────────────────
# WHY Loguru?  Zero-config structured logging.  The sink here writes to a
# rotating file (max 10 MB, keep 5 backups) — safe for small disks.
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger.remove()  # drop default stderr handler
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    level="INFO",
)
logger.add(
    os.path.join(LOG_DIR, "orchestra_{time:YYYY-MM-DD}.log"),
    rotation="10 MB",
    retention=5,
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
    level="DEBUG",
)

# ── App startup / shutdown ─────────────────────────────────────────────────────

_startup_time: float = 0.0

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_time
    _startup_time = time.time()
    logger.info("Orchestra-Agent API starting up")
    init_db()
    logger.info("Database initialised at {}", os.path.abspath("orchestra.db"))
    yield
    logger.info("Orchestra-Agent API shutting down")


app = FastAPI(
    title="Orchestra-Agent API",
    description="AI task planning backend — LangGraph pipeline exposed over HTTP",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in real production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ─────────────────────────────────────────────────

class OrchestrateRequest(BaseModel):
    user_request: str
    dry_run: bool = False   # if True, plan only — don't write to DB


class SubTaskOut(BaseModel):
    title: str
    description: str
    required_skills: list[str]
    estimated_hours: float
    difficulty: str
    priority: str
    assigned_to: Optional[str] = None
    deadline: Optional[str] = None
    match_score: Optional[float] = None
    db_task_id: Optional[int] = None


class OrchestrateResponse(BaseModel):
    status: str
    task_count: int
    subtasks: list[SubTaskOut]
    final_report: str
    elapsed_seconds: float


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    memory_mb: float
    cpu_percent: float
    db: dict


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check():
    """
    Lightweight liveness + readiness probe.
    Safe to call every 30 s from Docker HEALTHCHECK or uptime monitors.
    Does NOT run any LangGraph code — just checks memory, CPU, and DB.
    """
    proc = psutil.Process(os.getpid())
    mem  = proc.memory_info().rss / 1_048_576   # bytes → MB
    cpu  = psutil.cpu_percent(interval=0.1)

    try:
        db_stats = get_db_stats()
        db_ok    = True
    except Exception as exc:
        logger.error("Health DB check failed: {}", exc)
        db_stats = {}
        db_ok    = False

    uptime = time.time() - _startup_time if _startup_time else 0

    logger.debug("Health check: mem={:.1f}MB cpu={:.1f}%", mem, cpu)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        uptime_seconds=round(uptime, 1),
        memory_mb=round(mem, 1),
        cpu_percent=round(cpu, 1),
        db=db_stats,
    )


@app.post("/orchestrate", response_model=OrchestrateResponse, tags=["AI Pipeline"])
def orchestrate(req: OrchestrateRequest, background_tasks: BackgroundTasks):
    """
    Run the full 4-node LangGraph pipeline synchronously.
    Returns structured JSON so Streamlit (or any client) can render it.

    The LangGraph import is deferred to inside the function so the API
    process starts fast even before langchain packages finish initialising.
    """
    logger.info("Orchestrate request: '{}'", req.user_request[:80])
    t0 = time.time()

    # Lazy import — keeps startup memory low
    try:
        from graph import run_orchestra
    except ImportError as exc:
        logger.error("graph.py import failed: {}", exc)
        raise HTTPException(status_code=503, detail=f"AI backend unavailable: {exc}")

    result = run_orchestra(req.user_request)

    if result.get("error"):
        logger.error("Pipeline error: {}", result["error"])
        raise HTTPException(status_code=422, detail=result["error"])

    assigned  = result.get("assigned_tasks", [])
    subtasks_out = []
    for at in assigned:
        sub = at["subtask"]
        subtasks_out.append(SubTaskOut(
            title=sub["title"],
            description=sub["description"],
            required_skills=sub["required_skills"],
            estimated_hours=sub["estimated_hours"],
            difficulty=sub.get("difficulty","Medium"),
            priority=sub.get("priority","Medium"),
            assigned_to=at.get("assigned_employee_name"),
            deadline=at.get("deadline"),
            match_score=at.get("match_score"),
            db_task_id=at.get("db_task_id"),
        ))

    elapsed = round(time.time() - t0, 2)
    logger.success("Pipeline done in {}s — {} tasks created", elapsed, len(subtasks_out))

    return OrchestrateResponse(
        status="ok",
        task_count=len(subtasks_out),
        subtasks=subtasks_out,
        final_report=result.get("final_report",""),
        elapsed_seconds=elapsed,
    )


@app.get("/", tags=["Meta"])
def root():
    return {"service": "Orchestra-Agent API", "version": "3.0.0",
            "docs": "/docs", "health": "/health"}