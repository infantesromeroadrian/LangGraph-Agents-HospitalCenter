"""
Endpoints para gestión de mensajes de conversación.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.memory.conversation_memory import conversation_memory
from src.web.auth import ensure_session_access, require_session_token
from src.web.rate_limit import enforce_read_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: UUID,
    limit: Optional[int] = Query(default=50, ge=1, le=500),
    _: Any = Depends(enforce_read_rate_limit),
    session_auth: dict = Depends(require_session_token),
):
    """
    Obtiene el historial de mensajes de una sesión.

    Args:
        session_id: UUID de la sesión
        limit: Número máximo de mensajes a retornar (1-500)

    Returns:
        dict con lista de mensajes

    Raises:
        HTTPException: Si hay error obteniendo los mensajes
    """
    try:
        ensure_session_access(session_auth, session_id)

        messages = await conversation_memory.get_messages(session_id=session_id, limit=limit)

        return {
            "success": True,
            "count": len(messages),
            "messages": [msg.to_dict() for msg in messages],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ [API] Error obteniendo mensajes (%s)", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener los mensajes.",
        ) from e
