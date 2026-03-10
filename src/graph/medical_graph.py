"""Construcción del grafo médico con LangGraph."""

import inspect
import logging
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from src.config.settings import settings
from src.graph.nodes import (
    consensus_node,
    emergency_response_node,
    specialist_chat_node,
    specialist_evaluation_node,
    triage_node,
)
from src.graph.state import MedicalGraphState

logger = logging.getLogger(__name__)


def route_after_triage(state: MedicalGraphState):
    """
    Router después del triaje: decide entre evaluación paralela o chat directo.

    Si necesita evaluación, retorna Send objects para fan-out.
    Si no, retorna el nombre del nodo para chat directo.

    Args:
        state: Estado actual

    Returns:
        Lista de Send objects para fan-out O string con nombre del nodo
    """
    from langgraph.types import Send

    from src.agents.agent_factory import AgentFactory

    if state.get("triage_data", {}).get("urgency", "").lower() == "urgente":
        logger.warning("⚠️ [Router] -> Ruta de emergencia")
        return "emergency_response"

    # Si necesita evaluación paralela y no hay especialista seleccionado
    if state["needs_parallel_evaluation"] and not state["selected_specialist"]:
        logger.info("ℹ️ [Router] -> Evaluación paralela (fan-out)")

        # Crear Send para cada especialista
        specialties = AgentFactory.get_available_specialties()
        sends = [
            Send("specialist_evaluation", {"specialty": specialty, "state": state})
            for specialty in specialties
        ]

        logger.info(f"ℹ️ [Router] {len(sends)} especialistas activados")
        return sends
    else:
        # Ir directo al chat con el especialista activo
        logger.info(f"ℹ️ [Router] -> Chat directo con {state['active_specialist']}")
        return "specialist_chat"


def should_continue_conversation(_state: MedicalGraphState) -> Literal["end"]:
    """
    Decide si la conversación debe continuar.

    The conversation should END after each specialist response.
    The next user message will start a new graph execution.

    Args:
        state: Estado actual

    Returns:
        Always "end" - wait for next user message
    """
    # Always end the graph execution after a response
    # The next user message will trigger a new graph execution
    logger.info("ℹ️ [Router] -> Finalizando turno de conversación")
    return "end"


async def create_medical_graph(checkpointer: AsyncPostgresSaver) -> Any:
    """
    Crea y configura el grafo de agentes médicos.

    Returns:
        Grafo compilado con checkpointer
    """
    try:
        logger.info("ℹ️ [Graph] Construyendo grafo médico")

        # Crear el grafo
        workflow = StateGraph(MedicalGraphState)

        # Agregar nodos
        workflow.add_node("triage", triage_node)
        workflow.add_node("emergency_response", emergency_response_node)
        workflow.add_node("specialist_evaluation", specialist_evaluation_node)
        workflow.add_node("consensus", consensus_node)
        workflow.add_node("specialist_chat", specialist_chat_node)

        # Definir punto de entrada
        workflow.set_entry_point("triage")

        # Router después de triaje: decide fan-out o chat directo
        # Retorna Send objects (fan-out) o string "specialist_chat"
        workflow.add_conditional_edges("triage", route_after_triage)

        # Todas las evaluaciones paralelas van a consenso
        workflow.add_edge("specialist_evaluation", "consensus")

        # Consenso decide y va a chat
        workflow.add_edge("consensus", "specialist_chat")

        # Emergencias finalizan el turno tras instrucciones inmediatas
        workflow.add_edge("emergency_response", END)

        # After specialist chat, always end and wait for next user message
        # This prevents infinite recursion loops
        workflow.add_edge("specialist_chat", END)

        # Compilar el grafo con checkpointer
        graph = workflow.compile(checkpointer=checkpointer)

        logger.info("✅ [Graph] Grafo médico construido exitosamente")

        return graph

    except Exception as e:
        logger.error(f"❌ [Graph] Error construyendo grafo: {e!s}")
        raise


async def create_postgres_checkpointer() -> tuple[
    AsyncPostgresSaver, AbstractAsyncContextManager[AsyncPostgresSaver]
]:
    """
    Crea el checkpointer PostgreSQL para persistencia durable.

    Returns:
        Checkpointer configurado y su context manager asociado
    """
    try:
        checkpoint_db_url = settings.CHECKPOINT_DB_URL or settings.DATABASE_URL
        if not checkpoint_db_url:
            raise ValueError("CHECKPOINT_DB_URL no está configurada")

        logger.info("ℹ️ [Checkpointer] Inicializando AsyncPostgresSaver")

        context_manager = AsyncPostgresSaver.from_conn_string(checkpoint_db_url)
        checkpointer = await context_manager.__aenter__()

        setup_result = checkpointer.setup()
        if inspect.isawaitable(setup_result):
            await setup_result

        logger.info("✅ [Checkpointer] AsyncPostgresSaver inicializado")

        return checkpointer, context_manager

    except Exception as e:
        logger.error(f"❌ [Checkpointer] Error: {e!s}")
        raise


class MedicalGraphManager:
    """Gestor del grafo médico para uso en la aplicación."""

    def __init__(self):
        """Inicializa el gestor."""
        self.graph: Any = None
        self._checkpointer: AsyncPostgresSaver | None = None
        self._checkpointer_context: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None
        logger.info("ℹ️ [GraphManager] Inicializado")

    async def initialize(self):
        """Inicializa el grafo."""
        if self.graph is None:
            try:
                (
                    self._checkpointer,
                    self._checkpointer_context,
                ) = await create_postgres_checkpointer()
                self.graph = await create_medical_graph(self._checkpointer)
                logger.info("✅ [GraphManager] Grafo inicializado")
            except Exception:
                await self.close()
                raise

    async def close(self):
        """Libera los recursos del grafo y del checkpointer."""
        self.graph = None
        self._checkpointer = None

        if self._checkpointer_context is not None:
            await self._checkpointer_context.__aexit__(None, None, None)
            self._checkpointer_context = None
            logger.info("✅ [GraphManager] Checkpointer cerrado")

    async def get_graph(self):
        """
        Obtiene el grafo (lo inicializa si es necesario).

        Returns:
            Grafo compilado
        """
        if self.graph is None:
            await self.initialize()
        return self.graph

    async def invoke(self, state: MedicalGraphState, config: dict[str, Any]) -> MedicalGraphState:
        """
        Ejecuta el grafo con un estado.

        Args:
            state: Estado inicial
            config: Configuración (debe incluir thread_id)

        Returns:
            Estado final
        """
        graph = await self.get_graph()
        assert graph is not None
        result = await graph.ainvoke(state, config)
        return result

    async def stream(self, state: MedicalGraphState, config: dict[str, Any]):
        """
        Ejecuta el grafo en modo streaming.

        Args:
            state: Estado inicial
            config: Configuración (debe incluir thread_id)

        Yields:
            Eventos del grafo
        """
        graph = await self.get_graph()
        assert graph is not None
        async for event in graph.astream(state, config):
            yield event


# Instancia global del gestor
medical_graph_manager = MedicalGraphManager()
