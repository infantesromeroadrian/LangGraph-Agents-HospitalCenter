"""Nodos del grafo de agentes médicos."""

import logging

from src.agents.agent_factory import AgentFactory
from src.agents.consensus_agent import ConsensusAgent
from src.agents.triage_agent import TriageAgent
from src.graph.state import MedicalGraphState
from src.models.message import Message

logger = logging.getLogger(__name__)


def _is_emergency_state(state: MedicalGraphState) -> bool:
    """Determina si el estado actual corresponde a una urgencia."""
    return state.get("triage_data", {}).get("urgency", "").lower() == "urgente"


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
    """Genera una respuesta inmediata y segura cuando el triaje detecta urgencia."""
    session_id = state["session_id"]
    triage_data = state.get("triage_data", {})
    recommended_specialties = triage_data.get("recommended_specialties", [])
    main_symptoms = triage_data.get("main_symptoms", [])

    specialty_hint = recommended_specialties[0] if recommended_specialties else "medicina_general"
    urgent_signs = [
        "dolor intenso o que empeora rápidamente",
        "dificultad para respirar",
        "fiebre alta o mal estado general",
        "sangrado abundante o anormal",
        "desmayo, confusión o debilidad marcada",
    ]

    if specialty_hint == "ginecologia":
        urgent_signs = [
            "dolor pélvico intenso o abdomen muy doloroso",
            "fiebre alta o escalofríos",
            "sangrado vaginal abundante o embarazo posible con dolor",
            "flujo muy maloliente con empeoramiento rápido",
            "vómitos, mareo intenso o sensación de desmayo",
        ]
    elif specialty_hint == "cardiologia":
        urgent_signs = [
            "dolor torácico opresivo o que se irradia",
            "falta de aire importante",
            "desmayo o casi desmayo",
            "sudor frío o palidez intensa",
            "palpitaciones con mareo severo",
        ]
    elif specialty_hint == "neurologia":
        urgent_signs = [
            "debilidad en un lado del cuerpo",
            "dificultad para hablar o entender",
            "convulsiones",
            "dolor de cabeza súbito muy intenso",
            "pérdida de conciencia o confusión aguda",
        ]

    symptoms_text = (
        ", ".join(main_symptoms) if main_symptoms else "síntomas potencialmente urgentes"
    )
    guidance = "\n".join(f"- {sign}" for sign in urgent_signs)
    message = Message(
        role="assistant",
        content=(
            "He detectado una situación que requiere valoración médica urgente.\n\n"
            f"Motivo principal identificado: {symptoms_text}.\n\n"
            "Qué hacer ahora:\n"
            "1. No continúes dependiendo solo de este chat para decidir.\n"
            "2. Busca atención médica presencial hoy mismo.\n"
            "3. Si estás sola, intenta avisar a una persona de confianza.\n\n"
            "Acude a urgencias o llama a emergencias si presentas cualquiera de estos signos:\n"
            f"{guidance}\n\n"
            "Si puedes desplazarte de forma segura, lleva una lista de tus síntomas, alergias, medicación y el tiempo de evolución."
        ),
        session_id=session_id,
        specialist_type="emergencias",
        metadata={
            "triage_data": triage_data,
            "recommended_specialty": specialty_hint,
            "emergency_routing": True,
        },
    )

    logger.warning("⚠️ [Emergency] Caso urgente derivado a respuesta de emergencia")
    return {
        "messages": [message],
        "needs_parallel_evaluation": False,
        "selected_specialist": None,
        "active_specialist": None,
        "metadata": {"emergency_routing": True},
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
                f"{reasoning}\n\n"
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
