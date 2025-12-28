"""
Endpoints para gestión de sesiones de conversación médica.
"""

import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.memory.conversation_memory import conversation_memory
from src.services.database_service import db_service

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Request para crear una nueva sesión."""

    patient_info: dict = {}
    medical_record_number: Optional[str] = None  # ✅ NUEVO - HC del paciente registrado


class SessionResponse(BaseModel):
    """Response de sesión creada."""

    success: bool
    session_id: str
    thread_id: str


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest):
    """
    Crea una nueva sesión de conversación médica.

    Args:
        request: Información del paciente (y opcionalmente medical_record_number)

    Returns:
        SessionResponse con IDs de sesión y thread

    Raises:
        HTTPException: Si hay error creando la sesión
    """
    try:
        session_id = uuid4()

        # Crear sesión en base de datos
        await conversation_memory.create_session(
            session_id=session_id, patient_info=request.patient_info
        )

        # ✅ NUEVO: Si se proporciona medical_record_number, asociar con paciente
        if request.medical_record_number:
            await db_service._ensure_pool()

            async with db_service.pool.acquire() as conn:
                # Obtener patient_id desde medical_record_number
                patient_row = await conn.fetchrow(
                    """
                    SELECT id FROM patients
                    WHERE medical_record_number = $1
                    """,
                    request.medical_record_number,
                )

                if patient_row:
                    # Actualizar sesión con patient_id
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET patient_id = $1
                        WHERE session_id = $2
                        """,
                        patient_row["id"],
                        session_id,
                    )

                    logger.info(
                        f"✅ [API] Sesión {session_id} asociada con paciente {request.medical_record_number}"
                    )
                else:
                    logger.warning(
                        f"⚠️ [API] Medical record number {request.medical_record_number} not found"
                    )

        logger.info(f"ℹ️ [API] Sesión creada: {session_id}")

        return SessionResponse(
            success=True, session_id=str(session_id), thread_id=f"thread_{session_id}"
        )

    except Exception as e:
        logger.error(f"❌ [API] Error creando sesión: {e!s}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID):
    """
    Obtiene información completa de una sesión.

    Args:
        session_id: UUID de la sesión

    Returns:
        dict con información de sesión y resumen conversacional

    Raises:
        HTTPException: Si la sesión no existe o hay error
    """
    try:
        session = await conversation_memory.get_session(session_id)

        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # Obtener resumen de la conversación
        summary = await conversation_memory.get_conversation_summary(session_id)

        return {"success": True, "session": session.to_dict(), "summary": summary}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Error obteniendo sesión: {e!s}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
