# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile  ·  Orchestra-Agent  ·  Production
# ─────────────────────────────────────────────────────────────────────────────
# WHY python:3.11-slim?
#   - ~50 MB base vs ~900 MB for the full image
#   - Contains only the CPython runtime + pip, nothing else
#   - No Debian dev tools (gcc, make) in the final image = smaller attack surface
#
# TWO-STAGE BUILD:
#   Stage 1 (builder)  — install all Python deps into a virtualenv
#   Stage 2 (runtime)  — copy only the venv into the clean slim base
#   Result: final image has no pip cache, no build tools → ~300 MB total
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps (needed to compile some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated venv so we can copy it cleanly to the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first → Docker layer cache means pip only re-runs
# when requirements.txt changes, not on every source code change
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Create a non-root user for security
RUN groupadd -r orchestra && useradd -r -g orchestra -m orchestra

WORKDIR /app

# Copy venv from builder (no gcc, no pip cache)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY . .

# Create data and log directories with correct ownership
RUN mkdir -p /data /app/logs \
 && chown -R orchestra:orchestra /app /data

# Environment variables
# DATA_DIR  — SQLite file lives on a Docker volume, not inside the container
# LOG_DIR   — log files also on a named volume
ENV DATA_DIR=/data \
    LOG_DIR=/app/logs \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Switch to non-root
USER orchestra

# Expose both services
EXPOSE 8501   
# Streamlit
EXPOSE 8000   
# FastAPI

# Health check — calls our /health endpoint every 30 s
# Start period 60 s gives LangGraph time to import on cold start
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# Default: run Streamlit (override with CMD in docker-compose for FastAPI)
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]