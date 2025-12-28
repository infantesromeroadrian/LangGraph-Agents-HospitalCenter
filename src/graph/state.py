"""Definición del estado del grafo LangGraph."""

from dataclasses import dataclass, field
from operator import add
from typing import Annotated, Optional
from uuid import UUID

from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message


@dataclass
class MedicalGraphState:
    """
    Estado del grafo de agentes médicos.

    Este estado se mantiene a lo largo de toda la conversación
    y se persiste en PostgreSQL mediante el checkpointer.
    """

    # Identificadores
    session_id: UUID
    thread_id: str

    # Historial de mensajes (se acumula con operator add)
    messages: Annotated[list[Message], add] = field(default_factory=list)

    # Evaluaciones de especialistas (se acumula con operator add)
    specialist_evaluations: Annotated[list[SpecialistEvaluation], add] = field(default_factory=list)

    # Estado de triaje
    triage_completed: bool = False
    triage_data: dict = field(default_factory=dict)

    # Decisión de consenso
    consensus_decision: Optional[dict] = None
    selected_specialist: Optional[str] = None

    # Especialista activo actual
    active_specialist: Optional[str] = None

    # Metadata del paciente
    patient_info: dict = field(default_factory=dict)

    # ✅ NUEVO: Contexto del paciente formateado para LLM
    # Este string se genera desde patient_info y se inyecta en el primer mensaje
    patient_context: Optional[str] = None

    # Control de flujo
    needs_parallel_evaluation: bool = True
    evaluation_round: int = 0
    conversation_active: bool = True

    # Metadata adicional
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convierte el estado a diccionario."""
        return {
            "session_id": str(self.session_id),
            "thread_id": self.thread_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "specialist_evaluations": [eval.to_dict() for eval in self.specialist_evaluations],
            "triage_completed": self.triage_completed,
            "triage_data": self.triage_data,
            "consensus_decision": self.consensus_decision,
            "selected_specialist": self.selected_specialist,
            "active_specialist": self.active_specialist,
            "patient_info": self.patient_info,
            "patient_context": self.patient_context,
            "needs_parallel_evaluation": self.needs_parallel_evaluation,
            "evaluation_round": self.evaluation_round,
            "conversation_active": self.conversation_active,
            "metadata": self.metadata,
        }
