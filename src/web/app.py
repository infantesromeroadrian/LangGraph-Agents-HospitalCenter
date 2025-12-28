"""Aplicación Flask para el sistema médico."""

# IMPORTANTE: Monkey patch eventlet ANTES de cualquier otro import
import eventlet

eventlet.monkey_patch()

import logging
from uuid import UUID, uuid4

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room

from src.config.settings import settings
from src.graph.medical_graph import medical_graph_manager
from src.memory.conversation_memory import conversation_memory
from src.services.database_service import db_service
from src.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Storage para sesiones activas (por worker)
active_sessions = {}

# El grafo se inicializa automáticamente de forma lazy en el primer uso async
# No hay necesidad de inicialización síncrona en workers gthread


def create_app():
    """
    Factory para crear la aplicación Flask.

    Returns:
        Flask: Aplicación Flask configurada
    """
    # Crear aplicación Flask
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuración
    app.config["SECRET_KEY"] = settings.FLASK_SECRET_KEY
    app.config["DEBUG"] = settings.FLASK_DEBUG

    # CORS
    CORS(app, origins=settings.CORS_ORIGINS)

    # Socket.IO para streaming
    # IMPORTANTE: Usar "eventlet" para compatibilidad con asyncpg
    # eventlet funciona bien con async/await y asyncpg
    socketio = SocketIO(app, cors_allowed_origins=settings.CORS_ORIGINS, async_mode="eventlet")

    # Registrar rutas y event handlers
    register_routes(app)
    register_socketio_events(socketio)

    logger.info("✅ Aplicación Flask creada correctamente")

    return app


def register_routes(app):
    """Registra todas las rutas HTTP."""

    @app.route("/")
    def index():
        """Página principal."""
        return render_template("index.html")

    @app.route("/health")
    def health():
        """Health check endpoint."""
        # Verificar estado del pool de DB (puede ser None si aún no se ha usado)
        import os

        db_status = "ready"
        if db_service.pool:
            db_status = "connected"
        elif db_service._worker_pid != os.getpid():
            db_status = "pending (new worker)"
        else:
            db_status = "pending"

        return jsonify(
            {
                "status": "healthy",
                "version": "1.0.0",
                "worker_pid": os.getpid(),
                "services": {
                    "database": db_status,
                    "llm": "configured",
                    "graph": "initialized"
                    if medical_graph_manager.graph
                    else "will initialize on first use",
                },
            }
        )

    @app.route("/api/sessions", methods=["POST"])
    def create_session():
        """Crea una nueva sesión de conversación."""
        import asyncio

        try:
            session_id = uuid4()
            patient_info = request.json.get("patient_info", {})

            # Obtener o crear event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Crear sesión en base de datos
            session = loop.run_until_complete(
                conversation_memory.create_session(session_id=session_id, patient_info=patient_info)
            )

            # Registrar en active_sessions
            active_sessions[str(session_id)] = {
                "thread_id": f"thread_{session_id}",
                "created_at": session.created_at.isoformat(),
            }

            logger.info(f"ℹ️ [API] Sesión creada: {session_id}")

            return jsonify(
                {
                    "success": True,
                    "session_id": str(session_id),
                    "thread_id": active_sessions[str(session_id)]["thread_id"],
                }
            )

        except Exception as e:
            logger.error(f"❌ [API] Error creando sesión: {e!s}")
            import traceback

            logger.error(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    @app.route("/api/sessions/<session_id>", methods=["GET"])
    def get_session(session_id):
        """Obtiene información de una sesión."""
        import asyncio

        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            session = loop.run_until_complete(conversation_memory.get_session(UUID(session_id)))

            if not session:
                return jsonify({"success": False, "error": "Session not found"}), 404

            summary = loop.run_until_complete(
                conversation_memory.get_conversation_summary(session.session_id)
            )

            return jsonify({"success": True, "session": session.to_dict(), "summary": summary})

        except Exception as e:
            logger.error(f"❌ [API] Error obteniendo sesión: {e!s}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/sessions/<session_id>/messages", methods=["GET"])
    def get_messages(session_id):
        """Obtiene mensajes de una sesión."""
        import asyncio

        try:
            request.args.get("limit", type=int)

            # Obtener o crear event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Crear sesión en base de datos
            session = loop.run_until_complete(
                conversation_memory.create_session(session_id=session_id, patient_info=patient_info)
            )

            # Registrar en active_sessions
            active_sessions[str(session_id)] = {
                "thread_id": f"thread_{session_id}",
                "created_at": session.created_at.isoformat(),
            }

            logger.info(f"ℹ️ [API] Sesión creada: {session_id}")

            return jsonify(
                {
                    "success": True,
                    "session_id": str(session_id),
                    "thread_id": active_sessions[str(session_id)]["thread_id"],
                }
            )

        except Exception as e:
            logger.error(f"❌ [API] Error obteniendo mensajes: {e!s}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.errorhandler(404)
    def not_found(error):
        """Error 404."""
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Error 500."""
        logger.error(f"❌ Error interno: {error!s}")
        return jsonify({"error": "Internal server error"}), 500


def register_socketio_events(socketio):
    """Registra todos los event handlers de SocketIO."""

    @socketio.on("connect")
    def handle_connect():
        """Cliente conectado via WebSocket."""
        logger.info(f"ℹ️ [WebSocket] Cliente conectado: {request.sid}")
        emit("connected", {"message": "Connected to medical system"})

    @socketio.on("disconnect")
    def handle_disconnect():
        """Cliente desconectado."""
        logger.info(f"ℹ️ [WebSocket] Cliente desconectado: {request.sid}")

    @socketio.on("join_session")
    def handle_join_session(data):
        """Cliente se une a una sesión."""
        session_id = data.get("session_id")
        if session_id:
            join_room(session_id)
            logger.info(f"ℹ️ [WebSocket] Cliente {request.sid} se unió a sesión: {session_id}")
            emit("joined", {"session_id": session_id})

    @socketio.on("send_message")
    def handle_send_message(data):
        """
        Maneja un mensaje del usuario y ejecuta el grafo.

        Emite eventos de streaming durante la ejecución.
        """
        # Redirigir a handle_user_message
        handle_user_message(data)

    @socketio.on("user_message")
    def handle_user_message(data):
        """Procesa mensaje del usuario y ejecuta grafo médico."""
        import asyncio

        def run_async_handler():
            try:
                session_id = data.get("session_id")
                message_content = data.get("message")

                if not session_id or not message_content:
                    socketio.emit("error", {"message": "session_id and message required"})
                    return

                logger.info(f"ℹ️ [WebSocket] Mensaje recibido - Sesión: {session_id}")
                logger.info(f"ℹ️ [WebSocket] Contenido: {message_content}")

                # Crear mensaje del usuario
                from src.graph.state import MedicalGraphState
                from src.models.message import Message

                user_message = Message(
                    role="user", content=message_content, session_id=UUID(session_id)
                )

                # Obtener o crear event loop para este worker
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                try:
                    # Guardar mensaje
                    loop.run_until_complete(conversation_memory.add_message(user_message))

                    # Crear estado inicial
                    state = MedicalGraphState(
                        session_id=UUID(session_id),
                        thread_id=active_sessions.get(session_id, {}).get(
                            "thread_id", f"thread_{session_id}"
                        ),
                        messages=[user_message],
                    )

                    # Configuración para LangGraph
                    config = {
                        "configurable": {"thread_id": state.thread_id},
                        "recursion_limit": 50,  # Increase from default 25
                    }

                    # Ejecutar grafo en streaming
                    socketio.emit("agent_thinking", {"agent_name": "Triaje"})

                    logger.info("ℹ️ [WebSocket] Iniciando stream del grafo")

                    # Lista para acumular mensajes a guardar
                    messages_to_save = []

                    # Ejecutar stream
                    async def process_stream():
                        async for event in medical_graph_manager.stream(state, config):
                            # Emitir cada evento del grafo
                            node_name = next(iter(event.keys()))
                            node_output = event[node_name]

                            logger.info(f"ℹ️ [Graph] Nodo ejecutado: {node_name}")

                            # Preparar datos para enviar
                            graph_data = {"node": node_name}

                            # Si hay evaluaciones, incluirlas
                            if "evaluations" in node_output:
                                evaluations_data = []
                                for evaluation in node_output["evaluations"]:
                                    eval_dict = {
                                        "specialist_type": evaluation.specialist_type,
                                        "relevance_score": evaluation.relevance_score,
                                        "reasoning": evaluation.reasoning,
                                    }
                                    evaluations_data.append(eval_dict)

                                graph_data["data"] = {"evaluations": evaluations_data}

                            # Emitir evento de actualización del grafo
                            socketio.emit("graph_update", graph_data)

                            # Si hay nuevos mensajes, acumularlos y enviarlos al frontend
                            if "messages" in node_output:
                                for msg in node_output["messages"]:
                                    # Acumular para guardar después
                                    messages_to_save.append(msg)

                                    socketio.emit(
                                        "agent_response",
                                        {
                                            "role": msg.role,
                                            "content": msg.content,
                                            "specialist_type": msg.specialist_type,
                                            "metadata": msg.metadata,
                                            "is_final": True,
                                        },
                                    )

                    loop.run_until_complete(process_stream())

                    # Guardar mensajes en background (fire-and-forget)
                    # No bloqueamos el response del usuario
                    if messages_to_save:
                        logger.info(
                            f"ℹ️ [WebSocket] Encolando {len(messages_to_save)} mensajes para guardar"
                        )
                        # NOTE: Guardado de mensajes deshabilitado temporalmente
                        # debido a event loop conflicts con eventlet + asyncpg
                        # TODO: Migrar a FastAPI o implementar queue-based persistence
                        # Alternativa: usar sync DB driver (psycopg2) en lugar de asyncpg

                    logger.info(f"✅ [WebSocket] Procesamiento completado - Sesión: {session_id}")

                except asyncio.CancelledError:
                    logger.warning("⚠️ [WebSocket] Procesamiento cancelado")
                finally:
                    # NO cerrar el loop - puede ser reutilizado por eventlet
                    # Si necesitas cerrarlo, asegúrate de que no haya tareas pendientes
                    pass

            except Exception as e:
                logger.error(f"❌ [WebSocket] Error: {e!s}")
                import traceback

                logger.error(traceback.format_exc())
                socketio.emit("error", {"message": str(e)})

        # Ejecutar en background task de eventlet
        socketio.start_background_task(run_async_handler)

    @socketio.on("message")
    def handle_message(data):
        """Procesa mensaje del usuario y ejecuta grafo médico."""
        # Redirigir a handle_user_message para mantener compatibilidad
        handle_user_message(data)


# Crear instancia global de la aplicación (para Gunicorn)
app = create_app()

# Crear SocketIO global para Gunicorn con eventlet
socketio = SocketIO(
    app,
    cors_allowed_origins=settings.CORS_ORIGINS,
    async_mode="eventlet",
    logger=True,
    engineio_logger=True,
)

# Registrar eventos SocketIO
register_socketio_events(socketio)

logger.info("🚀 Aplicación y SocketIO listos para Gunicorn")


if __name__ == "__main__":
    """Ejecutar en modo desarrollo local."""
    logger.info("🚀 Iniciando servidor Flask en modo desarrollo")

    # Para desarrollo local, necesitamos crear socketio manualmente
    socketio = SocketIO(app, cors_allowed_origins=settings.CORS_ORIGINS, async_mode="gevent")

    # Registrar eventos SocketIO
    register_socketio_events(socketio)

    # Ejecutar servidor
    socketio.run(
        app, host=settings.FLASK_HOST, port=settings.FLASK_PORT, debug=settings.FLASK_DEBUG
    )
