"""Tests para el sistema de memoria."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from src.memory.conversation_memory import ConversationMemory
from src.models.message import Message
from src.models.session import Session


@pytest.fixture
def mock_db_service():
    """Mock del servicio de base de datos."""
    service = AsyncMock()
    service.create_session = AsyncMock()
    service.get_session = AsyncMock()
    service.update_session = AsyncMock()
    service.save_message = AsyncMock()
    service.get_messages = AsyncMock(return_value=[])
    service.get_active_sessions = AsyncMock(return_value=[])
    return service


@pytest.fixture
def sample_session():
    """Sesión de prueba."""
    return Session(
        session_id=uuid4(),
        patient_info={"age": 35, "gender": "M"}
    )


@pytest.fixture
def sample_messages():
    """Mensajes de prueba."""
    session_id = uuid4()

    return [
        Message(
            role="user",
            content="Tengo dolor de cabeza",
            session_id=session_id
        ),
        Message(
            role="assistant",
            content="¿Desde cuándo tienes el dolor?",
            session_id=session_id,
            specialist_type="triaje"
        ),
        Message(
            role="user",
            content="Desde hace 2 días",
            session_id=session_id
        )
    ]


class TestConversationMemory:
    """Tests para ConversationMemory."""

    @pytest.mark.asyncio
    async def test_create_session(self, mock_db_service, sample_session):
        """Test creación de sesión."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.create_session.return_value = sample_session

        result = await memory.create_session(
            session_id=sample_session.session_id,
            patient_info=sample_session.patient_info
        )

        assert result.session_id == sample_session.session_id
        mock_db_service.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self, mock_db_service, sample_session):
        """Test obtención de sesión."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.get_session.return_value = sample_session

        result = await memory.get_session(sample_session.session_id)

        assert result is not None
        assert result.session_id == sample_session.session_id
        mock_db_service.get_session.assert_called_once_with(sample_session.session_id)

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_db_service):
        """Test obtención de sesión inexistente."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.get_session.return_value = None

        result = await memory.get_session(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_add_message(self, mock_db_service, sample_messages):
        """Test agregar mensaje."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.save_message.return_value = True

        result = await memory.add_message(sample_messages[0])

        assert result is True
        mock_db_service.save_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_messages(self, mock_db_service, sample_messages):
        """Test obtener mensajes."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.get_messages.return_value = sample_messages

        result = await memory.get_messages(sample_messages[0].session_id)

        assert len(result) == 3
        assert result[0].role == "user"
        mock_db_service.get_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_conversation_summary(self, mock_db_service, sample_messages):
        """Test obtener resumen de conversación."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.get_messages.return_value = sample_messages

        summary = await memory.get_conversation_summary(sample_messages[0].session_id)

        assert "session_id" in summary
        assert "total_messages" in summary
        assert summary["total_messages"] == 3
        assert summary["user_messages"] == 2
        assert summary["assistant_messages"] == 1
        assert "triaje" in summary["specialists_involved"]

    @pytest.mark.asyncio
    async def test_clear_session(self, mock_db_service):
        """Test limpiar sesión."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.update_session.return_value = True

        session_id = uuid4()
        result = await memory.clear_session(session_id)

        assert result is True
        mock_db_service.update_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_history_for_llm(self, mock_db_service, sample_messages):
        """Test formato de historial para LLM."""
        memory = ConversationMemory(db=mock_db_service)

        mock_db_service.get_messages.return_value = sample_messages

        formatted = await memory.format_history_for_llm(
            session_id=sample_messages[0].session_id,
            max_messages=10
        )

        assert isinstance(formatted, list)
        assert len(formatted) == 3
        assert all("role" in msg and "content" in msg for msg in formatted)

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, mock_db_service):
        """Test obtener sesiones activas."""
        memory = ConversationMemory(db=mock_db_service)

        mock_sessions = [
            Session(session_id=uuid4()),
            Session(session_id=uuid4())
        ]

        mock_db_service.get_active_sessions.return_value = mock_sessions

        result = await memory.get_active_sessions(limit=10)

        assert len(result) == 2
        mock_db_service.get_active_sessions.assert_called_once_with(10)


class TestSession:
    """Tests para el modelo Session."""

    def test_session_initialization(self):
        """Test inicialización de sesión."""
        session = Session()

        assert session.session_id is not None
        assert session.is_active is True
        assert session.triage_completed is False
        assert session.selected_specialist is None

    def test_session_mark_triage_completed(self):
        """Test marcar triaje completado."""
        session = Session()
        initial_updated_at = session.updated_at

        session.mark_triage_completed()

        assert session.triage_completed is True
        assert session.updated_at > initial_updated_at

    def test_session_set_specialist(self):
        """Test asignar especialista."""
        session = Session()

        session.set_specialist("cardiologia")

        assert session.selected_specialist == "cardiologia"

    def test_session_deactivate(self):
        """Test desactivar sesión."""
        session = Session()

        session.deactivate()

        assert session.is_active is False

    def test_session_to_dict(self):
        """Test conversión a diccionario."""
        session = Session()
        session_dict = session.to_dict()

        assert "session_id" in session_dict
        assert "created_at" in session_dict
        assert "is_active" in session_dict
        assert session_dict["is_active"] is True


@pytest.mark.integration
class TestMemoryIntegration:
    """Tests de integración de memoria con PostgreSQL."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requiere PostgreSQL running")
    async def test_full_conversation_flow(self):
        """Test flujo completo de conversación (requiere DB real)."""
        # Este test requiere PostgreSQL funcionando
        # Se ejecutará en entorno de integración
        pass

