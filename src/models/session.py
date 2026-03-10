"""Modelo de sesión de conversación."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Session:
    """Representa una sesión de conversación con un paciente."""

    session_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    patient_info: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    is_active: bool = True
    selected_specialist: Optional[str] = None
    triage_completed: bool = False
    consensus_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convierte la sesión a diccionario."""
        return {
            "session_id": str(self.session_id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "patient_info": self.patient_info,
            "metadata": self.metadata,
            "is_active": self.is_active,
            "selected_specialist": self.selected_specialist,
            "triage_completed": self.triage_completed,
            "consensus_data": self.consensus_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Crea una sesión desde un diccionario."""
        return cls(
            session_id=UUID(data["session_id"]) if "session_id" in data else uuid4(),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(UTC),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(UTC),
            patient_info=data.get("patient_info", {}),
            metadata=data.get("metadata", {}),
            is_active=data.get("is_active", True),
            selected_specialist=data.get("selected_specialist"),
            triage_completed=data.get("triage_completed", False),
            consensus_data=data.get("consensus_data", {}),
        )

    def update(self):
        """Actualiza el timestamp de última modificación."""
        self.updated_at = datetime.now(UTC)

    def mark_triage_completed(self):
        """Marca el triaje como completado."""
        self.triage_completed = True
        self.update()

    def set_specialist(self, specialist_type: str):
        """Asigna un especialista a la sesión."""
        self.selected_specialist = specialist_type
        self.update()

    def deactivate(self):
        """Desactiva la sesión."""
        self.is_active = False
        self.update()
