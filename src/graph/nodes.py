"""Nodos del grafo de agentes médicos."""

import logging

from langgraph.types import Send

from src.agents.agent_factory import AgentFactory
from src.agents.consensus_agent import ConsensusAgent
from src.agents.triage_agent import TriageAgent
from src.graph.state import MedicalGraphState
from src.models.message import Message

logger = logging.getLogger(__name__)


async def triage_node(state: MedicalGraphState) -> dict:
    """
    Nodo de triaje inicial.

    Analiza la consulta del paciente y prepara la evaluación paralela.

    Args:
        state: Estado actual del grafo

    Returns:
        Actualizaciones al estado
    """
    try:
        logger.info(f"ℹ️ [Triaje] Iniciando análisis - Sesión {state.session_id}")

        # Obtener el último mensaje del usuario
        user_messages = [msg for msg in state.messages if msg.role == "user"]

        if not user_messages:
            logger.warning("⚠️ [Triaje] No hay mensajes del usuario")
            return {"triage_completed": False}

        last_user_message = user_messages[-1]

        # Crear agente de triaje con LLM service
        from src.services.llm_service import llm_service

        triage_agent = TriageAgent(llm_service=llm_service)

        # ✅ NUEVO: Pasar contexto del paciente al agente
        # Realizar análisis de triaje
        triage_result = await triage_agent.evaluate(
            message=last_user_message,
            session_id=state.session_id,
            patient_context=state.patient_context,
        )

        # Crear mensaje de respuesta del triaje
        triage_message = Message(
            role="assistant",
            content=triage_result["summary"],
            session_id=state.session_id,
            specialist_type="triaje",
            metadata=triage_result,
        )

        logger.info(
            f"ℹ️ [Triaje] Análisis completado - Síntomas: {len(triage_result.get('symptoms', []))}"
        )

        return {
            "messages": [triage_message],
            "triage_completed": True,
            "triage_data": triage_result,
            "needs_parallel_evaluation": True,
        }

    except Exception as e:
        logger.error(f"❌ [Triaje] Error: {e!s}")
        error_message = Message(
            role="assistant",
            content="Lo siento, hubo un error en el análisis inicial. Por favor, inténtalo de nuevo.",
            session_id=state.session_id,
            specialist_type="triaje",
            metadata={"error": str(e)},
        )
        return {"messages": [error_message], "triage_completed": False}


def fan_out_to_specialists(state: MedicalGraphState) -> list[Send]:
    """
    Fan-out: Envía la consulta a todos los especialistas en paralelo.

    Esta función usa la Send API de LangGraph para ejecutar
    múltiples nodos especialistas en paralelo.

    Args:
        state: Estado actual del grafo

    Returns:
        Lista de Send objetos para ejecución paralela
    """
    try:
        logger.info("ℹ️ [Fan-out] Enviando a especialistas en paralelo")

        # Obtener todos los especialistas disponibles
        specialties = AgentFactory.get_available_specialties()

        # Crear Send para cada especialista
        sends = [
            Send("specialist_evaluation", {"specialty": specialty, "state": state})
            for specialty in specialties
        ]

        logger.info(f"ℹ️ [Fan-out] {len(sends)} especialistas activados")

        return sends

    except Exception as e:
        logger.error(f"❌ [Fan-out] Error: {e!s}")
        return []


async def specialist_evaluation_node(data: dict) -> dict:
    """
    Nodo de evaluación de un especialista individual.

    Se ejecuta en paralelo para cada especialista.

    Args:
        data: Datos con specialty y state

    Returns:
        Evaluación del especialista
    """
    specialty = data["specialty"]
    state: MedicalGraphState = data["state"]

    try:
        logger.info(f"ℹ️ [{specialty}] Evaluando caso")

        # Crear agente especialista
        agent = AgentFactory.create_agent(specialty)

        if agent is None:
            logger.error(f"❌ [{specialty}] No se pudo crear agente")
            return {}

        # Obtener último mensaje del usuario
        user_messages = [msg for msg in state.messages if msg.role == "user"]

        if not user_messages:
            return {}

        last_user_message = user_messages[-1]

        # ✅ NUEVO: Pasar contexto del paciente al especialista
        # Evaluar relevancia
        evaluation = await agent.evaluate(
            message=last_user_message,
            session_id=state.session_id,
            patient_context=state.patient_context,
        )

        logger.info(
            f"ℹ️ [{specialty}] Evaluación completada - Relevancia: {evaluation.relevance_score:.1f}"
        )

        return {"specialist_evaluations": [evaluation]}

    except Exception as e:
        logger.error(f"❌ [{specialty}] Error: {e!s}")
        return {}


async def consensus_node(state: MedicalGraphState) -> dict:
    """
    Nodo de consenso.

    Analiza todas las evaluaciones de especialistas y decide
    cuál debe atender al paciente.

    Args:
        state: Estado actual del grafo

    Returns:
        Decisión de consenso
    """
    try:
        logger.info(f"ℹ️ [Consenso] Analizando {len(state.specialist_evaluations)} evaluaciones")

        # Crear agente de consenso
        consensus_agent = ConsensusAgent()

        # Seleccionar mejor especialista
        decision = await consensus_agent.select_specialist(evaluations=state.specialist_evaluations)

        # Crear mensaje de respuesta
        selected = decision["selected_specialist"]
        confidence = decision["confidence"]
        reasoning = decision["reasoning"]

        consensus_message = Message(
            role="assistant",
            content=(
                f"Basándome en tu consulta, recomiendo que hables con "
                f"**{selected.replace('_', ' ').title()}**.\n\n"
                f"{reasoning}\n\n"
                f"Confianza: {confidence * 100:.0f}%"
            ),
            session_id=state.session_id,
            specialist_type="consenso",
            metadata=decision,
        )

        logger.info(f"ℹ️ [Consenso] Decisión tomada - {selected} (confianza={confidence:.2f})")

        return {
            "messages": [consensus_message],
            "consensus_decision": decision,
            "selected_specialist": selected,
            "active_specialist": selected,
            "needs_parallel_evaluation": False,
        }

    except Exception as e:
        logger.error(f"❌ [Consenso] Error: {e!s}")
        error_message = Message(
            role="assistant",
            content="Lo siento, hubo un error al procesar las evaluaciones.",
            session_id=state.session_id,
            specialist_type="consenso",
            metadata={"error": str(e)},
        )
        return {"messages": [error_message], "needs_parallel_evaluation": False}


async def specialist_chat_node(state: MedicalGraphState) -> dict:
    """
    Nodo de conversación con especialista seleccionado.

    Maneja la conversación continua con el especialista asignado.

    Args:
        state: Estado actual del grafo

    Returns:
        Respuesta del especialista
    """
    try:
        specialty = state.active_specialist

        if not specialty:
            logger.warning("⚠️ [Chat] No hay especialista activo")
            return {}

        logger.info(f"ℹ️ [{specialty}] Generando respuesta")

        # Crear agente especialista
        agent = AgentFactory.create_agent(specialty)

        if agent is None:
            return {}

        # Obtener último mensaje del usuario
        user_messages = [msg for msg in state.messages if msg.role == "user"]

        if not user_messages:
            return {}

        last_user_message = user_messages[-1]

        # Generar respuesta conversacional
        response = await agent.chat(
            message=last_user_message.content,  # Pasar contenido como string
            session_id=state.session_id,
            history=state.messages,
        )

        # Crear mensaje de respuesta
        response_message = Message(
            role="assistant",
            content=response,
            session_id=state.session_id,
            specialist_type=specialty,
        )

        logger.info(f"ℹ️ [{specialty}] Respuesta generada")

        return {"messages": [response_message]}

    except Exception as e:
        logger.error(f"❌ [Chat] Error: {e!s}")
        error_message = Message(
            role="assistant",
            content="Lo siento, hubo un error al generar la respuesta.",
            session_id=state.session_id,
            specialist_type=state.active_specialist or "sistema",
        )
        return {"messages": [error_message]}
