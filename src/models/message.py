"""Modelo de mensaje para conversaciones."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Optional
from uuid import UUID, uuid4


@dataclass
class Message:
    """Representa un mensaje en la conversación."""

    role: Literal["user", "assistant", "system"]
    content: str
    message_id: UUID = field(default_factory=uuid4)
    session_id: Optional[UUID] = None
    specialist_type: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convierte el mensaje a diccionario."""
        return {
            "role": self.role,
            "content": self.content,
            "message_id": str(self.message_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "specialist_type": self.specialist_type,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Crea un mensaje desde un diccionario."""
        return cls(
            role=data["role"],
            content=data["content"],
            message_id=UUID(data["message_id"]) if "message_id" in data else uuid4(),
            session_id=UUID(data["session_id"]) if data.get("session_id") else None,
            specialist_type=data.get("specialist_type"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(UTC),
            metadata=data.get("metadata", {}),
        )

    def to_langchain_format(self) -> dict:
        """Convierte a formato compatible con LangChain."""
        return {"role": self.role, "content": self.content}
