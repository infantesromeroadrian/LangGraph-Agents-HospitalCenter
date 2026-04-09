"""Sistema de memoria conversacional."""

import logging
from typing import Optional
from uuid import UUID

from src.models.message import Message
from src.models.session import Session
from src.services.database_service import DatabaseService, db_service

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Gestor de memoria conversacional.

    Maneja el almacenamiento y recuperación de mensajes y sesiones
    en PostgreSQL, complementando el checkpointer de LangGraph.
    """

    def __init__(self, db: Optional[DatabaseService] = None):
        """
        Inicializa el gestor de memoria.

        Args:
            db: Servicio de base de datos (usa global si no se provee)
        """
        self.db = db or db_service
        logger.info("ℹ️ ConversationMemory inicializado")

    async def create_session(
        self, session_id: UUID, patient_info: Optional[dict] = None
    ) -> Session:
        """
        Crea una nueva sesión.

        Args:
            session_id: ID único de la sesión
            patient_info: Información del paciente

        Returns:
            Sesión creada
        """
        try:
            session = Session(session_id=session_id, patient_info=patient_info or {})

            await self.db.create_session(session)

            logger.info(f"ℹ️ Sesión creada: {session_id}")
            return session

        except Exception as e:
            logger.error(f"❌ Error creando sesión: {e!s}")
            raise

    async def get_session(self, session_id: UUID) -> Optional[Session]:
        """
        Obtiene una sesión por ID.

        Args:
            session_id: ID de la sesión

        Returns:
            Sesión o None
        """
        try:
            session = await self.db.get_session(session_id)

            if session:
                logger.info(f"ℹ️ Sesión recuperada: {session_id}")
            else:
                logger.warning(f"⚠️ Sesión no encontrada: {session_id}")

            return session

        except Exception as e:
            logger.error(f"❌ Error obteniendo sesión: {e!s}")
            return None

    async def update_session(self, session_id: UUID, updates: dict) -> bool:
        """
        Actualiza una sesión.

        Args:
            session_id: ID de la sesión
            updates: Campos a actualizar

        Returns:
            True si se actualizó correctamente
        """
        try:
            session = await self.db.get_session(session_id)
            if not session:
                logger.warning("Session not found for update: %s", session_id)
                return False

            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            await self.db.update_session(session)
            logger.info("Session updated: %s", session_id)
            return True

        except Exception as e:
            logger.error("Error updating session: %s", e)
            return False

    async def add_message(self, message: Message) -> bool:
        """
        Agrega un mensaje a la sesión.

        Args:
            message: Mensaje a guardar

        Returns:
            True si se guardó correctamente
        """
        try:
            await self.db.save_message(message)

            logger.info(f"ℹ️ Mensaje guardado - Sesión: {message.session_id}, Rol: {message.role}")

            return True

        except Exception as e:
            logger.error(f"❌ Error guardando mensaje: {e!s}")
            return False

    async def get_messages(self, session_id: UUID, limit: Optional[int] = None) -> list[Message]:
        """
        Obtiene mensajes de una sesión.

        Args:
            session_id: ID de la sesión
            limit: Número máximo de mensajes (None = todos)

        Returns:
            Lista de mensajes ordenados cronológicamente
        """
        try:
            messages = await self.db.get_messages(session_id, limit)

            logger.info(f"ℹ️ {len(messages)} mensajes recuperados - Sesión: {session_id}")

            return messages

        except Exception as e:
            logger.error(f"❌ Error obteniendo mensajes: {e!s}")
            return []

    async def get_conversation_summary(self, session_id: UUID) -> dict:
        """
        Obtiene un resumen de la conversación.

        Args:
            session_id: ID de la sesión

        Returns:
            Resumen con estadísticas
        """
        try:
            messages = await self.get_messages(session_id)

            user_messages = [m for m in messages if m.role == "user"]
            assistant_messages = [m for m in messages if m.role == "assistant"]

            specialists = {m.specialist_type for m in assistant_messages if m.specialist_type}

            summary = {
                "session_id": str(session_id),
                "total_messages": len(messages),
                "user_messages": len(user_messages),
                "assistant_messages": len(assistant_messages),
                "specialists_involved": list(specialists),
                "first_message_at": messages[0].created_at if messages else None,
                "last_message_at": messages[-1].created_at if messages else None,
            }

            logger.info(f"ℹ️ Resumen generado - Sesión: {session_id}")

            return summary

        except Exception as e:
            logger.error(f"❌ Error generando resumen: {e!s}")
            return {"error": str(e)}

    async def clear_session(self, session_id: UUID) -> bool:
        """
        Limpia todos los mensajes de una sesión.

        Args:
            session_id: ID de la sesión

        Returns:
            True si se limpió correctamente
        """
        try:
            # Marcar sesión como inactiva
            await self.update_session(session_id, {"is_active": False})

            logger.info(f"ℹ️ Sesión marcada como inactiva: {session_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error limpiando sesión: {e!s}")
            return False

    async def get_active_sessions(self, limit: int = 10) -> list[Session]:
        """
        Obtiene sesiones activas recientes.

        Args:
            limit: Número máximo de sesiones

        Returns:
            Lista de sesiones activas
        """
        try:
            sessions = await self.db.get_active_sessions(limit)

            logger.info(f"ℹ️ {len(sessions)} sesiones activas recuperadas")

            return sessions

        except Exception as e:
            logger.error(f"❌ Error obteniendo sesiones activas: {e!s}")
            return []

    async def format_history_for_llm(self, session_id: UUID, max_messages: int = 10) -> list[dict]:
        """
        Formatea el historial de mensajes para el LLM.

        Args:
            session_id: ID de la sesión
            max_messages: Máximo de mensajes a incluir

        Returns:
            Lista de mensajes formateados para OpenAI
        """
        try:
            messages = await self.get_messages(session_id, limit=max_messages)

            # Formatear para API de OpenAI
            formatted = [msg.to_langchain_format() for msg in messages]

            logger.info(f"ℹ️ {len(formatted)} mensajes formateados para LLM - Sesión: {session_id}")

            return formatted

        except Exception as e:
            logger.error(f"❌ Error formateando historial: {e!s}")
            return []


# Instancia global
conversation_memory = ConversationMemory()
