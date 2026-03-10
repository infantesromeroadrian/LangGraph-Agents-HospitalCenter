"""Definición del estado del grafo LangGraph."""

from operator import add
from typing import Annotated, Any, TypedDict
from uuid import UUID

from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message


class MedicalGraphState(TypedDict):
    """Estado del grafo de agentes médicos compatible con LangGraph 1.0."""

    session_id: UUID
    thread_id: str
    messages: Annotated[list[Message], add]
    specialist_evaluations: Annotated[list[SpecialistEvaluation], add]
    triage_completed: bool
    triage_data: dict[str, Any]
    consensus_decision: dict[str, Any] | None
    selected_specialist: str | None
    active_specialist: str | None
    patient_info: dict[str, Any]
    patient_context: str | None
    needs_parallel_evaluation: bool
    evaluation_round: int
    conversation_active: bool
    metadata: dict[str, Any]


def create_initial_state(
    session_id: UUID,
    thread_id: str,
    *,
    messages: list[Message] | None = None,
    specialist_evaluations: list[SpecialistEvaluation] | None = None,
    triage_completed: bool = False,
    triage_data: dict[str, Any] | None = None,
    consensus_decision: dict[str, Any] | None = None,
    selected_specialist: str | None = None,
    active_specialist: str | None = None,
    patient_info: dict[str, Any] | None = None,
    patient_context: str | None = None,
    needs_parallel_evaluation: bool = True,
    evaluation_round: int = 0,
    conversation_active: bool = True,
    metadata: dict[str, Any] | None = None,
) -> MedicalGraphState:
    """Crea un estado completo con defaults seguros para LangGraph."""
    return {
        "session_id": session_id,
        "thread_id": thread_id,
        "messages": list(messages or []),
        "specialist_evaluations": list(specialist_evaluations or []),
        "triage_completed": triage_completed,
        "triage_data": dict(triage_data or {}),
        "consensus_decision": consensus_decision,
        "selected_specialist": selected_specialist,
        "active_specialist": active_specialist,
        "patient_info": dict(patient_info or {}),
        "patient_context": patient_context,
        "needs_parallel_evaluation": needs_parallel_evaluation,
        "evaluation_round": evaluation_round,
        "conversation_active": conversation_active,
        "metadata": dict(metadata or {}),
    }


def state_to_dict(state: MedicalGraphState) -> dict[str, Any]:
    """Convierte el estado a un diccionario serializable."""
    return {
        "session_id": str(state["session_id"]),
        "thread_id": state["thread_id"],
        "messages": [msg.to_dict() for msg in state["messages"]],
        "specialist_evaluations": [
            evaluation.to_dict() for evaluation in state["specialist_evaluations"]
        ],
        "triage_completed": state["triage_completed"],
        "triage_data": state["triage_data"],
        "consensus_decision": state["consensus_decision"],
        "selected_specialist": state["selected_specialist"],
        "active_specialist": state["active_specialist"],
        "patient_info": state["patient_info"],
        "patient_context": state["patient_context"],
        "needs_parallel_evaluation": state["needs_parallel_evaluation"],
        "evaluation_round": state["evaluation_round"],
        "conversation_active": state["conversation_active"],
        "metadata": state["metadata"],
    }
