"""
Endpoints para gestión de mensajes de conversación.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.memory.conversation_memory import conversation_memory

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: UUID, limit: Optional[int] = Query(default=50, ge=1, le=500)):
    """
    Obtiene el historial de mensajes de una sesión.

    ✅ BUG CORREGIDO: Este endpoint tenía un bug en app.py (línea 196-198)
    donde usaba `patient_info` sin definir. Ahora usa correctamente
    `conversation_memory.get_messages()`.

    Args:
        session_id: UUID de la sesión
        limit: Número máximo de mensajes a retornar (1-500)

    Returns:
        dict con lista de mensajes

    Raises:
        HTTPException: Si hay error obteniendo los mensajes
    """
    try:
        # ✅ CORRECTO: Usar get_messages en vez de create_session
        messages = await conversation_memory.get_messages(session_id=session_id, limit=limit)

        return {
            "success": True,
            "count": len(messages),
            "messages": [msg.to_dict() for msg in messages],
        }

    except Exception as e:
        logger.error(f"❌ [API] Error obteniendo mensajes: {e!s}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
