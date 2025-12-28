# ============================================================================
# Dockerfile con UV - Medical Center
# ============================================================================
# VENTAJAS:
# - 10-100x más rápido que pip
# - Usa uv.lock para reproducibilidad
# - Cache más eficiente
# - Menor tamaño de imagen
# ============================================================================

# Stage 1: Builder con UV
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (for Docker layer caching)
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --python /opt/venv/bin/python --no-cache -r pyproject.toml

# ============================================================================
# Stage 2: Runtime (slim)
# ============================================================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 medicaluser && \
    mkdir -p /app /app/logs && \
    chown -R medicaluser:medicaluser /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=medicaluser:medicaluser src/ ./src/
COPY --chown=medicaluser:medicaluser pyproject.toml ./

# Switch to non-root user
USER medicaluser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose port
EXPOSE 5000

# Run application with Uvicorn (FastAPI)
# ✅ MIGRADO: Ya no usamos Gunicorn + Eventlet
CMD ["uvicorn", \
     "src.web.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
