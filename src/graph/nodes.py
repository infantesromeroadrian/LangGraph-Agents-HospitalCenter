"""Nodos del grafo de agentes médicos."""

import logging

from src.agents.agent_factory import AgentFactory
from src.agents.consensus_agent import ConsensusAgent
from src.agents.triage_agent import TriageAgent
from src.graph.state import MedicalGraphState
from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message
from src.safety import apply_output_guard, build_emergency_message, detect_red_flags

logger = logging.getLogger(__name__)


def _is_emergency_state(state: MedicalGraphState) -> bool:
    """Determina si el estado actual corresponde a una urgencia."""
    return state.get("triage_data", {}).get("urgency", "").lower() == "urgente"


RED_FLAG_LOOKBACK_USER_MESSAGES = 3


def _recent_user_text(messages: list[Message]) -> str:
    """Texto de los últimos mensajes del paciente (sin fiarse de ningún campo del estado)."""
    user_texts = [m.content for m in messages if m.role == "user" and isinstance(m.content, str)]
    return "\n".join(user_texts[-RED_FLAG_LOOKBACK_USER_MESSAGES:])


async def safety_gate_node(state: MedicalGraphState) -> dict:
    """Puerta de seguridad determinista: se ejecuta ANTES de triaje y especialistas.

    No usa LLM ni lee ningún campo del estado que no sean los mensajes del paciente, así que
    ni el modelo ni el texto del usuario (p. ej. "no escales", "ignora lo anterior") pueden
    desactivarla. Cualquier signo de alarma deriva a `emergency_response` con el 112.
    """
    text = _recent_user_text(state["messages"])
    flags = detect_red_flags(text)
    categories = [f.category for f in flags]
    if categories:
        logger.warning("⚠️ [SafetyGate] Signos de alarma detectados: %s", categories)
    return {
        "metadata": {
            "red_flags": categories,
            "safety_gate": "escalated" if categories else "clear",
        },
    }


async def triage_node(state: MedicalGraphState) -> dict:
    """
    Nodo de triaje inicial.

    Analiza la consulta del paciente y prepara la evaluación paralela.

    Args:
        state: Estado actual del grafo

    Returns:
        Actualizaciones al estado
    """
    session_id = state["session_id"]
    messages = state["messages"]
    patient_context = state["patient_context"]

    try:
        if state.get("triage_completed") and state.get("active_specialist"):
            logger.info(
                f"ℹ️ [Triaje] Reutilizando especialista activo: {state['active_specialist']}"
            )
            return {"needs_parallel_evaluation": False}

        logger.info(f"ℹ️ [Triaje] Iniciando análisis - Sesión {session_id}")

        # Obtener el último mensaje del usuario
        user_messages = [msg for msg in messages if msg.role == "user"]

        if not user_messages:
            logger.warning("⚠️ [Triaje] No hay mensajes del usuario")
            return {"triage_completed": False}

        last_user_message = user_messages[-1]

        # Crear agente de triaje con LLM service
        from src.services.llm_service import llm_service

        triage_agent = TriageAgent(llm_service=llm_service)

        # Realizar análisis de triaje
        triage_result = await triage_agent.evaluate(
            message=last_user_message,
            session_id=session_id,
            patient_context=patient_context,
        )

        # Crear mensaje de respuesta del triaje
        triage_message = Message(
            role="assistant",
            content=triage_result["summary"],
            session_id=session_id,
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
            session_id=session_id,
            specialist_type="triaje",
            metadata={"error": "internal_processing_error"},
        )
        return {"messages": [error_message], "triage_completed": False}


async def emergency_response_node(state: MedicalGraphState) -> dict:
    """Respuesta inmediata y segura ante una urgencia.

    Si la puerta determinista detectó signos de alarma, el mensaje es estático (nunca generado
    por el LLM) e incluye el 112. Si solo el triaje con LLM marcó "urgente", se usa el mensaje
    genérico, que también incluye el 112.
    """
    session_id = state["session_id"]
    triage_data = state.get("triage_data", {})
    gate_meta = state.get("metadata", {}) or {}
    categories = list(gate_meta.get("red_flags", []) or [])

    from src.safety.red_flags import RedFlag

    flags = [RedFlag(category=c, rule="safety_gate") for c in categories]
    message = Message(
        role="assistant",
        content=build_emergency_message(flags),
        session_id=session_id,
        specialist_type="emergencias",
        metadata={
            "emergency_routing": True,
            "deterministic": bool(categories),
            "red_flags": categories,
            "emergency_number": "112",
        },
    )

    logger.warning("⚠️ [Emergency] Caso urgente derivado a respuesta de emergencia")
    return {
        "messages": [message],
        "triage_data": {**triage_data, "urgency": "urgente", "red_flags": categories},
        "needs_parallel_evaluation": False,
        "selected_specialist": None,
        "active_specialist": None,
        "metadata": {**gate_meta, "emergency_routing": True},
    }


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

    session_id = state["session_id"]
    messages = state["messages"]
    patient_context = state["patient_context"]

    try:
        logger.info(f"ℹ️ [{specialty}] Evaluando caso")

        # Crear agente especialista
        agent = AgentFactory.create_agent(specialty)

        if agent is None:
            logger.error(f"❌ [{specialty}] No se pudo crear agente")
            return {}

        # Obtener último mensaje del usuario
        user_messages = [msg for msg in messages if msg.role == "user"]

        if not user_messages:
            return {}

        last_user_message = user_messages[-1]

        # Evaluar relevancia
        evaluation = await agent.evaluate(
            message=last_user_message,
            session_id=session_id,
            patient_context=patient_context,
        )

        if not isinstance(evaluation, SpecialistEvaluation):
            logger.error(f"❌ [{specialty}] Evaluación con formato inesperado")
            return {}

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
    session_id = state["session_id"]
    evaluations = state["specialist_evaluations"]

    try:
        logger.info(f"ℹ️ [Consenso] Analizando {len(evaluations)} evaluaciones")

        # Crear agente de consenso
        consensus_agent = ConsensusAgent()

        # Seleccionar mejor especialista
        decision = await consensus_agent.select_specialist(evaluations=evaluations)

        # Crear mensaje de respuesta
        selected = decision["selected_specialist"]
        confidence = decision["confidence"]
        reasoning = decision["reasoning"]

        consensus_message = Message(
            role="assistant",
            content=(
                f"Basándome en tu consulta, recomiendo que hables con "
                f"**{selected.replace('_', ' ').title()}**.\n\n"
                f"{apply_output_guard(str(reasoning)).text}\n\n"
                f"Confianza: {confidence * 100:.0f}%"
            ),
            session_id=session_id,
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
            session_id=session_id,
            specialist_type="consenso",
            metadata={"error": "internal_processing_error"},
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
    specialty = state["active_specialist"]
    session_id = state["session_id"]
    messages = state["messages"]
    patient_context = state["patient_context"]

    try:
        if not specialty:
            logger.warning("⚠️ [Chat] No hay especialista activo")
            return {}

        logger.info(f"ℹ️ [{specialty}] Generando respuesta")

        # Crear agente especialista
        agent = AgentFactory.create_agent(specialty)

        if agent is None:
            return {}

        # Obtener último mensaje del usuario
        user_messages = [msg for msg in messages if msg.role == "user"]

        if not user_messages:
            return {}

        last_user_message = user_messages[-1]

        # Generar respuesta conversacional
        response = await agent.chat(
            message=last_user_message,
            session_id=session_id,
            history=messages,
            patient_context=patient_context,
        )

        # Crear mensaje de respuesta
        response_message = Message(
            role="assistant",
            content=response,
            session_id=session_id,
            specialist_type=specialty,
        )

        logger.info(f"ℹ️ [{specialty}] Respuesta generada")

        return {"messages": [response_message]}

    except Exception as e:
        logger.error(f"❌ [Chat] Error: {e!s}")
        error_message = Message(
            role="assistant",
            content="Lo siento, hubo un error al generar la respuesta.",
            session_id=session_id,
            specialist_type=specialty or "sistema",
        )
        return {"messages": [error_message]}
