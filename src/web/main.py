"""
Aplicación FastAPI para el sistema médico.

Migrado desde Flask para resolver incompatibilidades de event loop
y mejorar performance con soporte async nativo.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config.settings import settings
from src.graph.medical_graph import medical_graph_manager
from src.services.database_service import db_service
from src.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """
    Lifecycle manager para startup y shutdown de la aplicación.

    Maneja la inicialización y limpieza de recursos:
    - Conexión a base de datos
    - Inicialización del grafo médico
    """
    # Startup
    logger.info("🚀 Iniciando Medical Center API (FastAPI)")

    settings.validate_config()
    logger.info("✅ Configuración crítica validada")

    # Inicializar servicios
    try:
        await db_service.connect()
        logger.info("✅ Base de datos conectada")
    except Exception as e:
        logger.error("❌ Error conectando base de datos (%s)", type(e).__name__)
        # No fallar el startup, el servicio se auto-reconectará

    # Inicializar grafo médico
    try:
        await medical_graph_manager.initialize()
        logger.info("✅ Grafo médico inicializado")
    except Exception as e:
        logger.error("❌ Error inicializando grafo (%s)", type(e).__name__)

    logger.info("✅ Servicios inicializados correctamente")

    yield

    # Shutdown
    logger.info("👋 Cerrando Medical Center API")
    await medical_graph_manager.close()
    await db_service.disconnect()
    logger.info("✅ Servicios cerrados correctamente")


# Crear aplicación FastAPI
app = FastAPI(
    title="LangGraph Medical Center API",
    description="Sistema de agentes médicos especializados con LangGraph y GPT-4o",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' cdn.jsdelivr.net d3js.org cdnjs.cloudflare.com; "
        "style-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com 'unsafe-inline'; "
        "font-src 'self' cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self' ws: wss:"
    )
    if settings.AUTH_COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Importar y registrar routers
# IMPORTANTE: Los imports van después de crear la app para evitar import circulares
from src.web.routers import health, messages, patients, sessions  # noqa: E402
from src.web.websocket import chat  # noqa: E402

app.include_router(health.router, tags=["Health"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])
app.include_router(messages.router, prefix="/api", tags=["Messages"])
app.include_router(patients.router, prefix="/api", tags=["Patients"])  # 📋 Gestión de pacientes
app.include_router(chat.router, tags=["WebSocket"])

# Static files (CSS, JS, imágenes)
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

# Templates Jinja2
templates = Jinja2Templates(directory="src/web/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Página principal de la aplicación web.

    Returns:
        Template HTML renderizado
    """
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})


@app.get("/admission", response_class=HTMLResponse)
async def admission_form(request: Request):
    """
    Formulario de admisión de pacientes.

    Esta página permite registrar nuevos pacientes antes de iniciar
    la consulta médica. Recopila datos personales, información médica
    y genera un número de historia clínica.

    Returns:
        Template HTML del formulario de admisión
    """
    del request
    return RedirectResponse(url="/", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> RedirectResponse:
    """Redirige el favicon clásico al recurso estático SVG."""
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Iniciando servidor FastAPI en modo desarrollo")

    uvicorn.run(
        "src.web.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
