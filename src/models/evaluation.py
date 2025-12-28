"""Modelo de evaluación de especialistas."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class SpecialistEvaluation:
    """Representa la evaluación de un especialista sobre un caso."""

    specialist_type: str
    relevance_score: float  # 0-100
    reasoning: str
    evaluation_id: UUID = field(default_factory=uuid4)
    session_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    evaluation_data: dict = field(default_factory=dict)
    confidence: float = 0.0
    key_symptoms: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validación post inicialización."""
        if not (0 <= self.relevance_score <= 100):
            raise ValueError(
                f"Relevance score must be between 0 and 100, got {self.relevance_score}"
            )
        if not self.specialist_type:
            raise ValueError("Specialist type cannot be empty")

    def to_dict(self) -> dict:
        """Convierte la evaluación a diccionario."""
        return {
            "specialist_type": self.specialist_type,
            "relevance_score": self.relevance_score,
            "reasoning": self.reasoning,
            "evaluation_id": str(self.evaluation_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "created_at": self.created_at.isoformat(),
            "evaluation_data": self.evaluation_data,
            "confidence": self.confidence,
            "key_symptoms": self.key_symptoms,
            "recommended_actions": self.recommended_actions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpecialistEvaluation":
        """Crea una evaluación desde un diccionario."""
        return cls(
            specialist_type=data["specialist_type"],
            relevance_score=data["relevance_score"],
            reasoning=data["reasoning"],
            evaluation_id=UUID(data["evaluation_id"]) if "evaluation_id" in data else uuid4(),
            session_id=UUID(data["session_id"]) if data.get("session_id") else None,
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.utcnow(),
            evaluation_data=data.get("evaluation_data", {}),
            confidence=data.get("confidence", 0.0),
            key_symptoms=data.get("key_symptoms", []),
            recommended_actions=data.get("recommended_actions", []),
        )

    def is_highly_relevant(self, threshold: float = 70.0) -> bool:
        """Determina si la evaluación es altamente relevante."""
        return self.relevance_score >= threshold
