# ============================================================================
# Dockerfile con UV - Medical Center
# ============================================================================

# Stage 1: Builder con UV
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv sync --frozen --no-dev --python /opt/venv/bin/python

# ============================================================================
# Stage 2: Runtime (slim)
# ============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 medicaluser && \
    mkdir -p /app /app/logs && \
    chown -R medicaluser:medicaluser /app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY --chown=medicaluser:medicaluser src/ ./src/
COPY --chown=medicaluser:medicaluser main.py pyproject.toml ./

LABEL org.opencontainers.image.title="LangGraph Medical Center" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.description="Multi-agent medical system with LangGraph"

USER medicaluser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

EXPOSE 5000

CMD ["uvicorn", \
     "src.web.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "127.0.0.1,::1"]
