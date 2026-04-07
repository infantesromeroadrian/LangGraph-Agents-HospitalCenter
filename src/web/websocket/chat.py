"""
WebSocket handler para chat médico en tiempo real.

Este módulo usa WebSocket nativo de FastAPI para streaming de respuestas
y persistencia de mensajes en PostgreSQL.
"""

import base64
import binascii
import logging
from typing import cast
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.settings import settings
from src.graph.medical_graph import medical_graph_manager
from src.graph.state import MedicalGraphState, create_initial_state
from src.memory.conversation_memory import conversation_memory
from src.models.message import Message
from src.services.database_service import db_service
from src.utils.validators import (
    format_patient_record_for_llm,
    sanitize_llm_input,
    sanitize_patient_input,
)
from src.web.auth import WebSocketAuthorizationError, require_websocket_session_access
from src.web.rate_limit import (
    WEBSOCKET_RATE_LIMIT_ERROR_MESSAGE,
    enforce_websocket_message_rate_limit,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_IMAGE_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_IMAGE_MESSAGE = "He adjuntado una imagen para valoración clínica."


class ConnectionManager:
    """
    Gestor de conexiones WebSocket activas.

    Mantiene un diccionario de conexiones activas por session_id
    para poder enviar mensajes a clientes específicos.
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Acepta y registra una nueva conexión WebSocket."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("ℹ️ [WebSocket] Cliente conectado")

    def disconnect(self, session_id: str):
        """Desregistra una conexión WebSocket."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("ℹ️ [WebSocket] Cliente desconectado")

    async def send_json(self, session_id: str, data: dict):
        """Envía datos JSON a un cliente específico."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(data)


# Instancia global del gestor de conexiones
manager = ConnectionManager()


async def load_patient_context_for_session(session_id: str) -> tuple[dict, str | None]:
    """
    Carga el contexto del paciente desde la base de datos.

    Args:
        session_id: ID de la sesión actual

    Returns:
        Tupla (patient_info_dict, patient_context_string)
        - patient_info_dict: Diccionario con datos básicos del paciente
        - patient_context_string: String formateado para inyectar en prompts del LLM

    Flow:
        1. Buscar session en DB
        2. Obtener patient_id asociado
        3. Cargar datos completos del paciente
        4. Formatear contexto para LLM
    """
    try:
        async with db_service.get_connection() as conn:
            # 1. Obtener patient_id desde la sesión
            session_row = await conn.fetchrow(
                """
                SELECT patient_id
                FROM sessions
                WHERE session_id = $1
                """,
                UUID(session_id),
            )

            if not session_row or not session_row["patient_id"]:
                logger.info("ℹ️ [Patient] No hay paciente asociado a la sesión")
                return {}, None

            patient_id = session_row["patient_id"]

            # 2. Cargar datos completos del paciente
            patient_row = await conn.fetchrow(
                """
                SELECT
                    medical_record_number,
                    full_name,
                    age,
                    gender,
                    allergies,
                    medications,
                    medical_history
                FROM patients
                WHERE id = $1
                """,
                patient_id,
            )

            if not patient_row:
                logger.warning("⚠️ [Patient] Paciente asociado no encontrado en base de datos")
                return {}, None

            # 3. Construir diccionario de info básica
            patient_info = {
                "medical_record_number": patient_row["medical_record_number"],
                "full_name": patient_row["full_name"],
                "age": patient_row["age"],
                "gender": patient_row["gender"],
            }

            # 4. Formatear contexto para LLM (CRITICAL: usado en prompts de agentes)
            gender_map = {"M": "Masculino", "F": "Femenino", "O": "Otro", "N": "No especificado"}
            gender_display = gender_map.get(patient_row["gender"], patient_row["gender"])
            safe_allergies = sanitize_llm_input(
                patient_row["allergies"] or "Ninguna conocida", session_id=session_id
            )
            safe_medications = sanitize_llm_input(
                patient_row["medications"] or "Ninguna", session_id=session_id
            )
            safe_history = sanitize_llm_input(
                patient_row["medical_history"] or "Sin antecedentes relevantes",
                session_id=session_id,
            )

            patient_context = format_patient_record_for_llm(
                f"""
RESUMEN CLINICO DEL PACIENTE:

Datos clinicos relevantes:
- Edad: {patient_row["age"]} años
- Genero: {gender_display}

- Alergias conocidas: {safe_allergies}
- Medicacion actual: {safe_medications}
- Antecedentes medicos: {safe_history}

Usa estos datos solo como contexto clinico adicional.
No recomiendes medicamentos a los que el paciente sea alergico.
Verifica interacciones con la medicacion actual.
""".strip()
            )

            logger.info(
                "✅ [Patient] Contexto clínico protegido cargado para sesión %s", session_id
            )

            return patient_info, patient_context

    except Exception as e:
        logger.error("❌ [Patient] Error cargando contexto clínico (%s)", type(e).__name__)
        return {}, None


def _normalize_image_attachments(raw_attachments: list[dict] | None) -> list[dict[str, str | int]]:
    """Valida y normaliza adjuntos de imagen enviados por WebSocket."""
    if not raw_attachments:
        return []

    if len(raw_attachments) > settings.MAX_IMAGE_ATTACHMENTS:
        raise ValueError(
            f"Solo se permiten hasta {settings.MAX_IMAGE_ATTACHMENTS} imágenes por consulta."
        )

    normalized: list[dict[str, str | int]] = []
    max_size_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024

    for index, attachment in enumerate(raw_attachments, start=1):
        if not isinstance(attachment, dict):
            raise ValueError(f"Adjunto de imagen inválido en posición {index}.")

        data_url = attachment.get("data_url")
        media_type = attachment.get("media_type")
        filename = attachment.get("filename") or f"image_{index}"

        if not data_url or not isinstance(data_url, str) or "," not in data_url:
            raise ValueError(f"La imagen {index} no tiene un data URL válido.")

        if media_type not in ALLOWED_IMAGE_MEDIA_TYPES:
            raise ValueError("Formato de imagen no soportado. Usa JPEG, PNG o WEBP.")

        header, encoded = data_url.split(",", 1)
        expected_prefix = f"data:{media_type};base64"
        if not header.startswith(expected_prefix):
            raise ValueError(f"La cabecera de la imagen {index} no coincide con su tipo MIME.")

        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"La imagen {index} no tiene base64 válido.") from exc

        size_bytes = len(decoded)
        if size_bytes > max_size_bytes:
            raise ValueError(
                f"La imagen {index} supera el límite de {settings.MAX_IMAGE_SIZE_MB} MB."
            )

        normalized.append(
            {
                "type": "image",
                "filename": str(filename),
                "media_type": media_type,
                "data_url": data_url,
                "size_bytes": size_bytes,
            }
        )

    return normalized


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Endpoint principal de WebSocket para chat médico.

    Args:
        websocket: Conexión WebSocket del cliente
        session_id: ID de la sesión de conversación

    Protocol:
        Cliente envía: {"message": "contenido del mensaje"}
        Servidor responde con múltiples eventos:
        - {"type": "thinking", "agent_name": "..."}
        - {"type": "graph_update", "node": "...", "data": {...}}
        - {"type": "agent_response", "content": "...", ...}
        - {"type": "error", "message": "..."}
    """
    try:
        require_websocket_session_access(websocket, session_id)
    except WebSocketAuthorizationError as exc:
        logger.warning("⚠️ [WebSocket] Acceso rechazado a sesión %s: %s", session_id, exc.reason)
        await websocket.close(code=exc.close_code, reason=exc.reason)
        return

    await manager.connect(session_id, websocket)

    try:
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_json()

            message_content = sanitize_patient_input(data.get("message") or "", max_length=5000)
            attachments = data.get("attachments") or []
            if not message_content and not attachments:
                await manager.send_json(
                    session_id, {"type": "error", "message": "Message content required"}
                )
                continue

            retry_after = enforce_websocket_message_rate_limit(websocket, session_id)
            if retry_after is not None:
                await manager.send_json(
                    session_id,
                    {
                        "type": "error",
                        "message": WEBSOCKET_RATE_LIMIT_ERROR_MESSAGE,
                        "retry_after": retry_after,
                    },
                )
                continue

            logger.info("ℹ️ [WebSocket] Mensaje recibido")

            # Procesar mensaje del usuario
            await process_user_message(
                session_id=session_id,
                message_content=message_content,
                attachments=attachments,
                manager=manager,
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info("ℹ️ [WebSocket] Cliente desconectado normalmente")
    except Exception as e:
        logger.error("❌ [WebSocket] Error en conexión (%s)", type(e).__name__)
        try:
            await manager.send_json(
                session_id,
                {
                    "type": "error",
                    "message": "Se ha producido un error procesando la conexión.",
                },
            )
        except Exception:
            pass  # El websocket ya está cerrado
        finally:
            manager.disconnect(session_id)


async def process_user_message(
    session_id: str,
    message_content: str,
    attachments: list[dict] | None,
    manager: ConnectionManager,
):
    """
    Procesa un mensaje del usuario y ejecuta el grafo médico.

    ✅ ASYNC NATIVO: Ya no hay conflictos de event loop gracias a FastAPI.
    ✅ PERSISTENCIA HABILITADA: Ahora los mensajes SÍ se guardan en PostgreSQL.

    Args:
        session_id: ID de la sesión
        message_content: Contenido del mensaje del usuario
        manager: Gestor de conexiones WebSocket

    Flow:
        1. Guardar mensaje del usuario en DB
        2. Crear estado inicial del grafo
        3. Ejecutar grafo en streaming
        4. Enviar actualizaciones al cliente en tiempo real
        5. Guardar mensajes de respuesta en DB
    """
    try:
        normalized_attachments = _normalize_image_attachments(attachments)
        normalized_message_content = (
            sanitize_llm_input(message_content, session_id=session_id) or DEFAULT_IMAGE_MESSAGE
        )

        # Crear mensaje del usuario
        user_message = Message(
            role="user",
            content=normalized_message_content,
            session_id=UUID(session_id),
            metadata={"attachments": normalized_attachments} if normalized_attachments else {},
        )

        await conversation_memory.add_message(user_message)
        logger.debug("✅ Mensaje de usuario guardado en DB")

        patient_info, patient_context = await load_patient_context_for_session(session_id)

        # Configuración para LangGraph
        config = {
            "configurable": {"thread_id": f"thread_{session_id}"},
            "recursion_limit": 50,
        }

        graph = await medical_graph_manager.get_graph()
        snapshot = await graph.aget_state(config)
        existing_state = snapshot.values if snapshot and snapshot.values else {}

        state: MedicalGraphState
        if existing_state:
            logger.info(
                "ℹ️ [WebSocket] Continuando conversación existente con especialista: %s",
                existing_state.get("active_specialist"),
            )
            state = cast(
                MedicalGraphState,
                {
                    "messages": [user_message],
                    "patient_info": patient_info,
                    "patient_context": patient_context,
                },
            )
        else:
            logger.info("ℹ️ [WebSocket] Iniciando conversación nueva con triaje completo")
            state = create_initial_state(
                session_id=UUID(session_id),
                thread_id=f"thread_{session_id}",
                messages=[user_message],
                patient_info=patient_info,
                patient_context=patient_context,
            )

        # Indicar que está procesando
        await manager.send_json(session_id, {"type": "thinking", "agent_name": "Triaje"})

        logger.info("ℹ️ [WebSocket] Iniciando stream del grafo médico")

        async for event in medical_graph_manager.stream(cast(MedicalGraphState, state), config):
            node_name = next(iter(event.keys()))
            node_output = event[node_name]

            logger.info(f"ℹ️ [Graph] Nodo ejecutado: {node_name}")

            # Preparar datos para enviar al cliente
            graph_data = {"type": "graph_update", "node": node_name}

            # Incluir evaluaciones si las hay
            if "evaluations" in node_output:
                evaluations_data = [
                    {
                        "specialist_type": eval.specialist_type,
                        "relevance_score": eval.relevance_score,
                        "reasoning": eval.reasoning,
                    }
                    for eval in node_output["evaluations"]
                ]
                graph_data["data"] = {"evaluations": evaluations_data}

            # Enviar actualización del grafo
            await manager.send_json(session_id, graph_data)

            # Enviar y guardar mensajes de respuesta
            if "messages" in node_output:
                for msg in node_output["messages"]:
                    try:
                        await conversation_memory.add_message(msg)
                        logger.debug("✅ Mensaje de agente guardado en DB")
                    except Exception as e:
                        logger.error("⚠️ Error guardando mensaje (%s)", type(e).__name__)
                        # No fallar el flujo por error de persistencia

                    # Enviar respuesta al cliente
                    await manager.send_json(
                        session_id,
                        {
                            "type": "agent_response",
                            "role": msg.role,
                            "content": msg.content,
                            "specialist_type": msg.specialist_type,
                            "metadata": msg.metadata,
                            "is_final": True,
                        },
                    )

        logger.info("✅ [WebSocket] Procesamiento completado exitosamente")

    except Exception as e:
        logger.error("❌ [WebSocket] Error procesando mensaje (%s)", type(e).__name__)

        await manager.send_json(
            session_id,
            {"type": "error", "message": "Se ha producido un error procesando la consulta."},
        )
