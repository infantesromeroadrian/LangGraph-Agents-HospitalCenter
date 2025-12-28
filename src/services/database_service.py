"""Servicio para interactuar con PostgreSQL."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

import asyncpg
from asyncpg import Pool

from src.config.settings import settings
from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message
from src.models.session import Session

logger = logging.getLogger(__name__)


class DatabaseService:
    """Servicio para operaciones de base de datos."""

    def __init__(self):
        """Inicializa el servicio de base de datos."""
        self.pool: Optional[Pool] = None
        self.database_url = settings.DATABASE_URL
        self._worker_pid = None  # Track worker process ID
        self._worker_pid = None  # Track worker process ID

    async def _ensure_pool(self):
        """
        Asegura que el pool esté disponible y sea válido para este worker.

        Crea un nuevo pool si:
        - No existe un pool
        - El PID cambió (nuevo worker de Gunicorn)
        """
        current_pid = os.getpid()

        # Si el PID cambió, cerrar el pool antiguo y crear uno nuevo
        if self._worker_pid != current_pid:
            if self.pool:
                try:
                    await self.pool.close()
                    logger.info(f"ℹ️ Pool anterior cerrado (PID: {self._worker_pid})")
                except Exception as e:
                    logger.warning(f"⚠️ Error cerrando pool anterior: {e}")
                self.pool = None

            self._worker_pid = current_pid
            logger.info(f"ℹ️ Worker PID actual: {current_pid}")

        # Crear pool si no existe
        if not self.pool:
            await self.connect()

    async def connect(self):
        """Establece conexión con la base de datos."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,  # Reducido para evitar sobrecarga con múltiples workers
                max_size=5,  # Cada worker tendrá su propio pool
                command_timeout=60,
                max_queries=5000,
                max_inactive_connection_lifetime=300,
            )
            logger.info(f"ℹ️ Pool PostgreSQL creado (PID: {os.getpid()})")
        except Exception as e:
            logger.error(f"❌ Error conectando a PostgreSQL: {e!s}")
            raise

    async def disconnect(self):
        """Cierra la conexión con la base de datos."""
        if self.pool:
            try:
                await self.pool.close()
                logger.info("ℹ️ Conexión a PostgreSQL cerrada")
            except Exception as e:
                logger.error(f"❌ Error cerrando pool: {e}")
            finally:
                self.pool = None

    @asynccontextmanager
    async def get_connection(self):
        """
        Context manager para obtener conexión del pool.

        Asegura que el pool sea válido para este worker antes de adquirir conexión.
        """
        await self._ensure_pool()

        connection = None
        try:
            connection = await self.pool.acquire(timeout=10.0)

            # Asegurar que la conexión esté en estado limpio
            try:
                await connection.execute("SELECT 1")  # Health check
            except Exception as e:
                logger.warning(f"⚠️ Conexión corrupta detectada: {e}")
                # Liberar la conexión corrupta
                await self.pool.release(connection)
                # Si la conexión está corrupta, reconectar pool
                await self.connect()
                # Obtener nueva conexión del pool renovado
                connection = await self.pool.acquire(timeout=10.0)

            yield connection

        except Exception as e:
            logger.error(f"❌ Error adquiriendo conexión: {e}")
            raise
        finally:
            if connection:
                try:
                    await self.pool.release(connection)
                except Exception as e:
                    logger.warning(f"⚠️ Error liberando conexión: {e}")

    # ==================== Operaciones de Session ====================

    async def create_session(self, session: Session) -> Session:
        """Crea una nueva sesión."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (
                    session_id, patient_info, metadata, is_active
                ) VALUES ($1, $2, $3, $4)
                """,
                session.session_id,
                json.dumps(session.patient_info),  # Serializar dict a JSON
                json.dumps(session.metadata),  # Serializar dict a JSON
                session.is_active,
            )
            logger.info(f"ℹ️ Sesión {session.session_id} creada")
            return session

    async def get_session(self, session_id: UUID) -> Optional[Session]:
        """Obtiene una sesión por ID."""
        async with self.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM sessions WHERE session_id = $1", session_id)

            if row:
                return Session.from_dict(dict(row))
            return None

    async def update_session(self, session: Session):
        """Actualiza una sesión."""
        session.update()
        async with self.get_connection() as conn:
            await conn.execute(
                """
                UPDATE sessions SET
                    updated_at = $2,
                    patient_info = $3,
                    metadata = $4,
                    is_active = $5
                WHERE session_id = $1
                """,
                session.session_id,
                session.updated_at,
                json.dumps(session.patient_info),  # Serializar dict a JSON
                json.dumps(session.metadata),  # Serializar dict a JSON
                session.is_active,
            )
            logger.debug(f"🐞 Sesión {session.session_id} actualizada")

    # ==================== Operaciones de Message ====================

    async def add_message(self, message: Message) -> Message:
        """Añade un mensaje a la conversación."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO messages (
                    message_id, session_id, role, content,
                    specialist_type, metadata, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                message.message_id,
                message.session_id,
                message.role,
                message.content,
                message.specialist_type,
                json.dumps(message.metadata)
                if message.metadata
                else json.dumps({}),  # Serializar dict a JSON
                message.created_at,
            )
            logger.debug(f"🐞 Mensaje añadido a sesión {message.session_id}")
            return message

    async def get_session_messages(
        self, session_id: UUID, limit: Optional[int] = None
    ) -> list[Message]:
        """Obtiene mensajes de una sesión."""
        async with self.get_connection() as conn:
            query = """
                SELECT * FROM messages
                WHERE session_id = $1
                ORDER BY created_at ASC
            """

            if limit:
                query += f" LIMIT {limit}"

            rows = await conn.fetch(query, session_id)

            return [Message.from_dict(dict(row)) for row in rows]

    # ==================== Operaciones de Evaluation ====================

    async def add_evaluation(self, evaluation: SpecialistEvaluation) -> SpecialistEvaluation:
        """Añade una evaluación de especialista."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO specialist_evaluations (
                    evaluation_id, session_id, specialist_type,
                    relevance_score, reasoning, evaluation_data, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                evaluation.evaluation_id,
                evaluation.session_id,
                evaluation.specialist_type,
                evaluation.relevance_score,
                evaluation.reasoning,
                evaluation.evaluation_data,
                evaluation.created_at,
            )
            logger.debug(
                f"🐞 Evaluación de {evaluation.specialist_type} añadida "
                f"(score: {evaluation.relevance_score})"
            )
            return evaluation

    async def get_session_evaluations(self, session_id: UUID) -> list[SpecialistEvaluation]:
        """Obtiene evaluaciones de una sesión."""
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM specialist_evaluations
                WHERE session_id = $1
                ORDER BY relevance_score DESC
                """,
                session_id,
            )

            return [SpecialistEvaluation.from_dict(dict(row)) for row in rows]

    # ==================== Operaciones de Limpieza ====================

    async def cleanup_old_sessions(self, days: int = 30):
        """Limpia sesiones antiguas inactivas."""
        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                DELETE FROM sessions
                WHERE is_active = FALSE
                AND updated_at < NOW() - INTERVAL '$1 days'
                """,
                days,
            )
            count = int(result.split()[-1])
            logger.info(f"ℹ️ {count} sesiones antiguas eliminadas")

    async def save_message(self, message) -> bool:
        """Alias para add_message para compatibilidad."""
        await self.add_message(message)
        return True

    async def get_messages(self, session_id: UUID, limit: Optional[int] = None):
        """Alias para get_session_messages para compatibilidad."""
        return await self.get_session_messages(session_id, limit)

    async def get_active_sessions(self, limit: int = 10):
        """Obtiene sesiones activas."""
        async with self.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM sessions
                WHERE is_active = TRUE
                ORDER BY updated_at DESC
                LIMIT $1
                """,
                limit,
            )

            from src.models.session import Session

            return [Session.from_dict(dict(row)) for row in rows]

    async def execute_query(self, query: str, *args):
        """
        ✅ NUEVO: Ejecuta una query genérica y retorna los resultados.

        Args:
            query: Query SQL con placeholders ($1, $2, etc.)
            *args: Parámetros para la query

        Returns:
            Lista de diccionarios con los resultados (o lista vacía si no hay)
        """
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]


# Instancia global del servicio
db_service = DatabaseService()
