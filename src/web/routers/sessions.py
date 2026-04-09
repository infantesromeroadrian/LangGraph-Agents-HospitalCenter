"""
Endpoints para gestión de sesiones de conversación médica.
"""

import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.memory.conversation_memory import conversation_memory
from src.services.database_service import db_service
from src.web.auth import (
    PATIENT_AUTH_COOKIE_NAME,
    SESSION_AUTH_COOKIE_NAME,
    create_session_access_token,
    ensure_session_access,
    require_patient_token,
    require_session_token,
    set_session_auth_cookie,
)
from src.web.rate_limit import enforce_read_rate_limit, enforce_write_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Request para crear una nueva sesión."""

    patient_info: dict = Field(default_factory=dict)
    medical_record_number: Optional[str] = None


class SessionResponse(BaseModel):
    """Response de sesión creada."""

    success: bool
    session_id: str
    thread_id: str


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    response: Response,
    _: Any = Depends(enforce_write_rate_limit),
    patient_auth: dict = Depends(require_patient_token),
):
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
        medical_record_number = request.medical_record_number or patient_auth.get(
            "medical_record_number"
        )

        if medical_record_number != patient_auth.get("medical_record_number"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para crear sesiones para otro paciente.",
            )

        # Crear sesión en base de datos
        await conversation_memory.create_session(
            session_id=session_id, patient_info=request.patient_info
        )

        # If medical_record_number provided, associate session with patient
        if medical_record_number:
            async with db_service.get_connection() as conn:
                patient_row = await conn.fetchrow(
                    """
                    SELECT id FROM patients
                    WHERE medical_record_number = $1
                    """,
                    medical_record_number,
                )

                if not patient_row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Paciente no encontrado para la sesión.",
                    )

                await conn.execute(
                    """
                    UPDATE sessions
                    SET patient_id = $1
                    WHERE session_id = $2
                    """,
                    patient_row["id"],
                    session_id,
                )

            session_token = create_session_access_token(session_id, medical_record_number)
            set_session_auth_cookie(response, session_token)

            logger.info("✅ [API] Sesión asociada correctamente con paciente autenticado")

        logger.info("ℹ️ [API] Sesión creada correctamente")

        return SessionResponse(
            success=True, session_id=str(session_id), thread_id=f"thread_{session_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ [API] Error creando sesión (%s)", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al crear la sesión.",
        ) from e


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    _: Any = Depends(enforce_read_rate_limit),
    session_auth: dict = Depends(require_session_token),
):
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
        ensure_session_access(session_auth, session_id)
        session = await conversation_memory.get_session(session_id)

        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # Obtener resumen de la conversación
        summary = await conversation_memory.get_conversation_summary(session_id)

        return {"success": True, "session": session.to_dict(), "summary": summary}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ [API] Error obteniendo sesión (%s)", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener la sesión.",
        ) from e


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """
    Cierra la sesion del paciente eliminando las cookies de autenticacion.

    Las cookies HttpOnly no son accesibles desde JavaScript, por lo que
    el cliente debe llamar a este endpoint para limpiarlas.
    """
    response.delete_cookie(
        key=PATIENT_AUTH_COOKIE_NAME,
        path="/",
    )
    response.delete_cookie(
        key=SESSION_AUTH_COOKIE_NAME,
        path="/",
    )
    return None
