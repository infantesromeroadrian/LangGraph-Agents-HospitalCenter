"""Modelo de mensaje para conversaciones."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Optional
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
        """Convierte a formato compatible con OpenAI/LangChain."""
        content = self.content
        attachments = self.get_image_attachments()
        if not attachments:
            return {"role": self.role, "content": content}

        content_parts: list[dict[str, Any]] = [
            {"type": "text", "text": content or "Imagen adjunta para valoración clínica."}
        ]
        for attachment in attachments:
            content_parts.append(
                {"type": "image_url", "image_url": {"url": attachment["data_url"]}}
            )

        return {"role": self.role, "content": content_parts}

    def get_image_attachments(self) -> list[dict[str, str]]:
        """Obtiene adjuntos de imagen desde metadata."""
        attachments = self.metadata.get("attachments", [])
        if not isinstance(attachments, list):
            return []

        valid_attachments: list[dict[str, str]] = []
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            data_url = attachment.get("data_url")
            media_type = attachment.get("media_type")
            if not data_url or not media_type:
                continue
            valid_attachments.append(
                {
                    "data_url": data_url,
                    "media_type": media_type,
                    "filename": attachment.get("filename", "image"),
                }
            )

        return valid_attachments

    def has_image_attachments(self) -> bool:
        """Indica si el mensaje incluye imágenes."""
        return bool(self.get_image_attachments())
