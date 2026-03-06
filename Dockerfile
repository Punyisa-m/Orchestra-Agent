# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile  ·  Orchestra-Agent  ·  Hybrid LLM Edition
# ─────────────────────────────────────────────────────────────────────────────
# Multi-stage build:
#   Stage 1 (builder)  — compile deps into isolated venv
#   Stage 2 (runtime)  — copy only the venv, no build tools, no pip cache
#   Final image:        ~320 MB  (vs ~950 MB single-stage)
#
# RAM targets (enforced by docker-compose, not here):
#   streamlit service   400 MB
#   api service         500 MB
#   Total               < 1 GB  ✓
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user — principle of least privilege
RUN groupadd -r orchestra && useradd -r -g orchestra -m orchestra

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

# /data = SQLite volume mount point  /app/logs = log files
RUN mkdir -p /data /app/logs \
 && chown -R orchestra:orchestra /app /data

# ── Environment defaults (override via docker-compose / HF Secrets) ──────────
# GOOGLE_API_KEY  — Gemini 1.5 Flash (primary)
# OPENAI_API_KEY  — GPT-4o-mini (fallback)
# OLLAMA_HOST     — local Ollama endpoint
# DATA_DIR        — SQLite location (auto-detected if unset)
ENV DATA_DIR=/data \
    LOG_DIR=/app/logs \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER orchestra

# Streamlit (default) → port 8501
# FastAPI (override)  → port 8000
EXPOSE 8501
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]