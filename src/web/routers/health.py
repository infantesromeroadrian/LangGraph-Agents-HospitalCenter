"""
Endpoints de health checks y métricas del sistema.
"""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.graph.medical_graph import medical_graph_manager
from src.services.database_service import db_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """
    Health check endpoint para validar el estado del sistema.

    Verifica:
    - Estado de la conexión a base de datos
    - Estado del grafo médico
    - Información del worker (PID)

    Returns:
        dict: Estado de salud con información de servicios
    """
    db_status = "ready"
    if db_service.pool:
        db_status = "connected"
    elif db_service._worker_pid != os.getpid():
        db_status = "pending (new worker)"
    else:
        db_status = "pending"

    return {
        "status": "healthy",
        "version": "2.0.0",
        "framework": "FastAPI",
        "worker_pid": os.getpid(),
        "services": {
            "database": db_status,
            "llm": "configured",
            "graph": "initialized" if medical_graph_manager.graph else "pending",
        },
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """
    Endpoint de métricas en formato Prometheus.

    TODO: Implementar métricas con prometheus_client
    - Sessions activas
    - Mensajes procesados
    - Latencia de respuesta
    - Uso de LLM (tokens)

    Returns:
        str: Métricas en formato Prometheus
    """
    # Placeholder - implementar en Fase 3
    return """
# HELP medical_uptime Sistema uptime en segundos
# TYPE medical_uptime gauge
medical_uptime 3600

# HELP medical_sessions_active Sesiones activas
# TYPE medical_sessions_active gauge
medical_sessions_active 0
    """.strip()
