"""
Aplicación FastAPI para el sistema médico.

Migrado desde Flask para resolver incompatibilidades de event loop
y mejorar performance con soporte async nativo.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

    # Inicializar servicios
    try:
        await db_service.connect()
        logger.info("✅ Base de datos conectada")
    except Exception as e:
        logger.error(f"❌ Error conectando base de datos: {e!s}")
        # No fallar el startup, el servicio se auto-reconectará

    # Inicializar grafo médico
    try:
        await medical_graph_manager.initialize()
        logger.info("✅ Grafo médico inicializado")
    except Exception as e:
        logger.error(f"❌ Error inicializando grafo: {e!s}")

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
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return templates.TemplateResponse("admission.html", {"request": request})


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
