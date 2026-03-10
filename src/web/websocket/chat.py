"""
WebSocket handler para chat médico en tiempo real.

✅ MIGRACIÓN EXITOSA: Este módulo reemplaza el sistema Flask-SocketIO + eventlet
con WebSocket nativo de FastAPI, resolviendo los conflictos de event loop
con asyncpg y habilitando la persistencia de mensajes.
"""

import base64
import binascii
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.settings import settings
from src.graph.medical_graph import medical_graph_manager
from src.graph.state import create_initial_state
from src.memory.conversation_memory import conversation_memory
from src.models.message import Message
from src.services.database_service import db_service

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
        logger.info(f"ℹ️ [WebSocket] Cliente conectado: {session_id}")

    def disconnect(self, session_id: str):
        """Desregistra una conexión WebSocket."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"ℹ️ [WebSocket] Cliente desconectado: {session_id}")

    async def send_json(self, session_id: str, data: dict):
        """Envía datos JSON a un cliente específico."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(data)


# Instancia global del gestor de conexiones
manager = ConnectionManager()


async def load_patient_context_for_session(session_id: str) -> tuple[dict, str | None]:
    """
    ✅ NUEVO: Carga el contexto del paciente desde la base de datos.

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
        # Asegurar que hay pool de conexiones
        await db_service._ensure_pool()

        async with db_service.pool.acquire() as conn:
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
                logger.info(f"ℹ️ [Patient] No patient associated with session: {session_id}")
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
                logger.warning(f"⚠️ [Patient] Patient ID {patient_id} not found in database")
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

            patient_context = f"""
INFORMACIÓN DEL PACIENTE (Historia Clínica: {patient_row["medical_record_number"]}):

Datos Personales:
- Nombre: {patient_row["full_name"]}
- Edad: {patient_row["age"]} años
- Género: {gender_display}

Alergias Conocidas:
{patient_row["allergies"] or "Ninguna conocida"}

Medicación Actual:
{patient_row["medications"] or "Ninguna"}

Antecedentes Médicos:
{patient_row["medical_history"] or "Sin antecedentes relevantes"}

IMPORTANTE: Considera esta información al hacer recomendaciones médicas.
No recomiendes medicamentos a los que el paciente sea alérgico.
Verifica interacciones con la medicación actual.
""".strip()

            logger.info(
                f"✅ [Patient] Contexto cargado: {patient_row['full_name']} ({patient_row['medical_record_number']})"
            )

            return patient_info, patient_context

    except Exception as e:
        logger.error(f"❌ [Patient] Error loading patient context: {e!s}")
        import traceback

        logger.error(traceback.format_exc())
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
    await manager.connect(session_id, websocket)

    try:
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_json()

            message_content = (data.get("message") or "").strip()
            attachments = data.get("attachments") or []
            if not message_content and not attachments:
                await manager.send_json(
                    session_id, {"type": "error", "message": "Message content required"}
                )
                continue

            logger.info(f"ℹ️ [WebSocket] Mensaje recibido - Sesión: {session_id}")

            # Procesar mensaje del usuario
            await process_user_message(
                session_id=session_id,
                message_content=message_content,
                attachments=attachments,
                manager=manager,
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info(f"ℹ️ [WebSocket] Cliente desconectado normalmente: {session_id}")
    except Exception as e:
        logger.error(f"❌ [WebSocket] Error: {e!s}")
        import traceback

        logger.error(traceback.format_exc())
        try:
            await manager.send_json(session_id, {"type": "error", "message": str(e)})
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
        normalized_message_content = message_content.strip() or DEFAULT_IMAGE_MESSAGE

        # Crear mensaje del usuario
        user_message = Message(
            role="user",
            content=normalized_message_content,
            session_id=UUID(session_id),
            metadata={"attachments": normalized_attachments} if normalized_attachments else {},
        )

        # ✅ GUARDAR MENSAJE - FUNCIONA PERFECTAMENTE CON FASTAPI
        await conversation_memory.add_message(user_message)
        logger.debug(f"✅ Mensaje de usuario guardado en DB: {session_id}")

        # ✅ NUEVO: CARGAR CONTEXTO DEL PACIENTE (si existe)
        patient_info, patient_context = await load_patient_context_for_session(session_id)

        # Configuración para LangGraph
        config = {
            "configurable": {"thread_id": f"thread_{session_id}"},
            "recursion_limit": 50,
        }

        graph = await medical_graph_manager.get_graph()
        snapshot = await graph.aget_state(config)
        existing_state = snapshot.values if snapshot and snapshot.values else {}

        if existing_state:
            logger.info(
                "ℹ️ [WebSocket] Continuando conversación existente con especialista: %s",
                existing_state.get("active_specialist"),
            )
            state = {
                "messages": [user_message],
                "patient_info": patient_info,
                "patient_context": patient_context,
            }
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

        # ✅ ASYNC STREAMING NATIVO - SIN CONFLICTOS DE EVENT LOOP
        async for event in medical_graph_manager.stream(state, config):
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
                    # ✅ GUARDAR MENSAJE EN DB - YA NO HAY PROBLEMAS DE EVENT LOOP
                    try:
                        await conversation_memory.add_message(msg)
                        logger.debug(f"✅ Mensaje de agente guardado en DB: {msg.role}")
                    except Exception as e:
                        logger.error(f"⚠️ Error guardando mensaje: {e!s}")
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

        logger.info(f"✅ [WebSocket] Procesamiento completado exitosamente: {session_id}")

    except Exception as e:
        logger.error(f"❌ [WebSocket] Error procesando mensaje: {e!s}")
        import traceback

        logger.error(traceback.format_exc())

        await manager.send_json(session_id, {"type": "error", "message": str(e)})
