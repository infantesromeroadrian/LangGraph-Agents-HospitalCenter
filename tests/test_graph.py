"""Tests para el grafo LangGraph."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from src.graph.nodes import (
    consensus_node,
    fan_out_to_specialists,
    specialist_chat_node,
    specialist_evaluation_node,
    triage_node,
)
from src.graph.state import MedicalGraphState
from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message


@pytest.fixture
def sample_state():
    """Estado del grafo de prueba."""
    session_id = uuid4()

    return MedicalGraphState(
        session_id=session_id,
        thread_id=f"thread_{session_id}",
        messages=[Message(role="user", content="Tengo dolor en el pecho", session_id=session_id)],
    )


@pytest.fixture
def sample_evaluations():
    """Evaluaciones de prueba."""
    return [
        SpecialistEvaluation(
            specialist_type="cardiologia",
            relevance_score=85.0,
            reasoning="Alta relevancia cardiovascular",
        ),
        SpecialistEvaluation(
            specialist_type="medicina_general",
            relevance_score=60.0,
            reasoning="Relevancia moderada",
        ),
        SpecialistEvaluation(
            specialist_type="neurologia",
            relevance_score=25.0,
            reasoning="Baja relevancia neurológica",
        ),
    ]


class TestMedicalGraphState:
    """Tests para MedicalGraphState."""

    def test_state_initialization(self):
        """Test inicialización del estado."""
        session_id = uuid4()
        thread_id = f"thread_{session_id}"

        state = MedicalGraphState(session_id=session_id, thread_id=thread_id)

        assert state.session_id == session_id
        assert state.thread_id == thread_id
        assert state.messages == []
        assert state.specialist_evaluations == []
        assert state.triage_completed is False
        assert state.selected_specialist is None

    def test_state_to_dict(self, sample_state):
        """Test conversión de estado a diccionario."""
        state_dict = sample_state.to_dict()

        assert "session_id" in state_dict
        assert "thread_id" in state_dict
        assert "messages" in state_dict
        assert "triage_completed" in state_dict
        assert isinstance(state_dict["messages"], list)


class TestTriageNode:
    """Tests para el nodo de triaje."""

    @pytest.mark.asyncio
    @patch("src.graph.nodes.TriageAgent")
    async def test_triage_node_success(self, mock_triage_class, sample_state):
        """Test ejecución exitosa del nodo de triaje."""
        # Mock del agente de triaje
        mock_agent = AsyncMock()
        # TriageAgent.evaluate() must return dict with 'summary' field (used in line 56 of nodes.py)
        mock_agent.evaluate = AsyncMock(
            return_value={
                "urgency": "no_urgente",
                "main_symptoms": ["dolor pecho"],
                "recommended_specialties": ["cardiologia"],
                "reasoning": "Evaluación cardiovascular recomendada",
                "summary": "Paciente presenta dolor torácico. Se recomienda evaluación por cardiología.",
                "symptoms": ["dolor pecho"],
            }
        )
        mock_triage_class.return_value = mock_agent

        # Ejecutar nodo
        updates = await triage_node(sample_state)

        assert "triage_completed" in updates
        assert updates["triage_completed"] is True
        assert "triage_data" in updates
        assert "needs_parallel_evaluation" in updates

    @pytest.mark.asyncio
    async def test_triage_node_no_messages(self):
        """Test nodo de triaje sin mensajes."""
        empty_state = MedicalGraphState(session_id=uuid4(), thread_id="test_thread")

        updates = await triage_node(empty_state)

        assert updates.get("triage_completed") is False


class TestFanOutNode:
    """Tests para fan-out a especialistas."""

    def test_fan_out_to_specialists(self, sample_state):
        """Test distribución a especialistas."""
        sends = fan_out_to_specialists(sample_state)

        assert isinstance(sends, list)
        assert (
            len(sends) == 8
        )  # 8 especialistas (medicina_general, cardiologia, neurologia, pediatria, dermatologia, traumatologia, psiquiatria, oncologia)

        # Verificar que son Send objects con estructura correcta
        for send in sends:
            assert hasattr(send, "node")
            assert send.node == "specialist_evaluation"
            # Send uses 'arg' attribute, not 'state'
            assert hasattr(send, "arg")
            assert "specialty" in send.arg
            assert "state" in send.arg


class TestSpecialistEvaluationNode:
    """Tests para nodo de evaluación de especialista."""

    @pytest.mark.asyncio
    @patch("src.graph.nodes.AgentFactory")
    async def test_specialist_evaluation_success(
        self, mock_factory, sample_state, sample_evaluations
    ):
        """Test evaluación exitosa de especialista."""
        # Mock del agente
        mock_agent = AsyncMock()
        mock_agent.evaluate.return_value = sample_evaluations[0]
        mock_factory.create_agent.return_value = mock_agent

        # Datos para el nodo
        data = {"specialty": "cardiologia", "state": sample_state}

        # Ejecutar nodo
        updates = await specialist_evaluation_node(data)

        assert "specialist_evaluations" in updates
        assert len(updates["specialist_evaluations"]) == 1
        assert updates["specialist_evaluations"][0].specialist_type == "cardiologia"

    @pytest.mark.asyncio
    async def test_specialist_evaluation_no_agent(self, sample_state):
        """Test evaluación cuando agente no se puede crear."""
        with patch("src.graph.nodes.AgentFactory.create_agent", return_value=None):
            data = {"specialty": "especialidad_inexistente", "state": sample_state}

            updates = await specialist_evaluation_node(data)

            assert updates == {}


class TestConsensusNode:
    """Tests para nodo de consenso."""

    @pytest.mark.asyncio
    @patch("src.graph.nodes.ConsensusAgent")
    async def test_consensus_node_success(
        self, mock_consensus_class, sample_state, sample_evaluations
    ):
        """Test ejecución exitosa del consenso."""
        # Agregar evaluaciones al estado
        sample_state.specialist_evaluations = sample_evaluations

        # Mock del agente de consenso
        mock_agent = AsyncMock()
        mock_agent.select_specialist.return_value = {
            "selected_specialist": "cardiologia",
            "confidence": 0.9,
            "reasoning": "Alta relevancia cardiovascular",
            "alternative_specialists": ["medicina_general"],
            "urgency_level": "media",
        }
        mock_consensus_class.return_value = mock_agent

        # Ejecutar nodo
        updates = await consensus_node(sample_state)

        assert "consensus_decision" in updates
        assert updates["selected_specialist"] == "cardiologia"
        assert updates["active_specialist"] == "cardiologia"
        assert updates["needs_parallel_evaluation"] is False

    @pytest.mark.asyncio
    async def test_consensus_node_no_evaluations(self, sample_state):
        """Test consenso sin evaluaciones."""
        updates = await consensus_node(sample_state)

        assert "consensus_decision" in updates or "messages" in updates


class TestSpecialistChatNode:
    """Tests para nodo de chat con especialista."""

    @pytest.mark.asyncio
    @patch("src.graph.nodes.AgentFactory")
    async def test_specialist_chat_success(self, mock_factory, sample_state):
        """Test chat exitoso con especialista."""
        # Configurar estado con especialista activo
        sample_state.active_specialist = "cardiologia"

        # Mock del agente
        mock_agent = AsyncMock()
        mock_agent.chat.return_value = "Entiendo tu preocupación. Dime más sobre el dolor."
        mock_factory.create_agent.return_value = mock_agent

        # Ejecutar nodo
        updates = await specialist_chat_node(sample_state)

        assert "messages" in updates
        assert len(updates["messages"]) == 1
        assert updates["messages"][0].role == "assistant"
        assert updates["messages"][0].specialist_type == "cardiologia"

    @pytest.mark.asyncio
    async def test_specialist_chat_no_active(self, sample_state):
        """Test chat sin especialista activo."""
        # No establecer active_specialist
        sample_state.active_specialist = None

        updates = await specialist_chat_node(sample_state)

        assert updates == {}


@pytest.mark.integration
class TestGraphIntegration:
    """Tests de integración del grafo completo."""

    @pytest.mark.asyncio
    async def test_full_graph_flow(self):
        """Test flujo completo del grafo (requiere LangGraph)."""
        # Este test requiere el grafo real compilado
        # Se implementará en test_system_integration.py
        pass
