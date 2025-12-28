"""Tests unitarios para agentes médicos."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseMedicalAgent
from src.agents.consensus_agent import ConsensusAgent
from src.agents.specialists.cardiology import CardiologyAgent
from src.agents.triage_agent import TriageAgent
from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message


@pytest.fixture
def mock_llm_service():
    """Mock del servicio LLM."""
    service = AsyncMock()
    service.complete_json = AsyncMock(return_value={
        "relevance_score": 75.0,
        "reasoning": "Test reasoning",
        "key_symptoms": ["test symptom"],
        "confidence": 0.8,
        "recommended_actions": ["test action"]
    })
    service.complete = AsyncMock(return_value="Test response")
    return service


@pytest.fixture
def sample_message():
    """Mensaje de prueba."""
    return Message(
        role="user",
        content="Tengo dolor en el pecho",
        session_id=uuid4()
    )


@pytest.fixture
def sample_triage_analysis():
    """Análisis de triaje de prueba."""
    return {
        "urgency": "no_urgente",
        "main_symptoms": ["dolor pecho"],
        "recommended_specialties": ["cardiologia"],
        "reasoning": "Síntomas cardiovasculares"
    }


class TestBaseMedicalAgent:
    """Tests para BaseMedicalAgent."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_llm_service):
        """Test inicialización de agente."""
        agent = CardiologyAgent(llm_service=mock_llm_service)

        assert agent.specialty == "cardiologia"
        assert agent.llm == mock_llm_service
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 0

    @pytest.mark.asyncio
    async def test_agent_evaluate(self, mock_llm_service, sample_message, sample_triage_analysis):
        """Test evaluación de agente."""
        agent = CardiologyAgent(llm_service=mock_llm_service)

        evaluation = await agent.evaluate(
            query=sample_message.content,
            triage_analysis=sample_triage_analysis,
            session_id=sample_message.session_id
        )

        assert isinstance(evaluation, SpecialistEvaluation)
        assert evaluation.specialist_type == "cardiologia"
        assert 0 <= evaluation.relevance_score <= 100
        assert evaluation.reasoning is not None

    @pytest.mark.asyncio
    async def test_agent_chat(self, mock_llm_service, sample_message):
        """Test conversación con agente."""
        agent = CardiologyAgent(llm_service=mock_llm_service)

        response = await agent.chat(
            message="¿Es grave?",
            conversation_history=[sample_message],
            session_context={}
        )

        assert isinstance(response, str)
        assert len(response) > 0
        mock_llm_service.complete.assert_called_once()


class TestTriageAgent:
    """Tests para TriageAgent."""

    @pytest.mark.asyncio
    async def test_triage_initialization(self, mock_llm_service):
        """Test inicialización de triaje."""
        agent = TriageAgent(llm_service=mock_llm_service)

        assert agent.specialty == "Triaje"
        assert len(agent.available_specialties) == 8

    @pytest.mark.asyncio
    async def test_triage_analyze(self, mock_llm_service):
        """Test análisis de triaje."""
        agent = TriageAgent(llm_service=mock_llm_service)

        mock_llm_service.complete_json.return_value = {
            "urgency": "urgente",
            "main_symptoms": ["dolor pecho", "dificultad respirar"],
            "recommended_specialties": ["cardiologia", "medicina_general"],
            "reasoning": "Síntomas cardiovasculares urgentes",
            "additional_info_needed": []
        }

        analysis = await agent.analyze(
            patient_query="Tengo dolor en el pecho y no puedo respirar bien",
            session_id=uuid4()
        )

        assert "urgency" in analysis
        assert "main_symptoms" in analysis
        assert "recommended_specialties" in analysis
        assert analysis["urgency"] == "urgente"

    def test_is_urgent(self):
        """Test detección de urgencia."""
        agent = TriageAgent()

        urgent_analysis = {"urgency": "urgente"}
        not_urgent_analysis = {"urgency": "no_urgente"}

        assert agent.is_urgent(urgent_analysis) is True
        assert agent.is_urgent(not_urgent_analysis) is False

    def test_get_top_specialties(self):
        """Test obtención de especialidades top."""
        agent = TriageAgent()

        analysis = {
            "recommended_specialties": ["cardiologia", "neurologia", "medicina_general", "pediatria"]
        }

        top_3 = agent.get_top_specialties(analysis, top_n=3)

        assert len(top_3) == 3
        assert top_3[0] == "cardiologia"


class TestConsensusAgent:
    """Tests para ConsensusAgent."""

    @pytest.fixture
    def sample_evaluations(self):
        """Evaluaciones de prueba."""
        return [
            SpecialistEvaluation(
                specialist_type="cardiologia",
                relevance_score=90.0,
                reasoning="Síntomas cardiovasculares claros"
            ),
            SpecialistEvaluation(
                specialist_type="medicina_general",
                relevance_score=70.0,
                reasoning="Consulta general posible"
            ),
            SpecialistEvaluation(
                specialist_type="neurologia",
                relevance_score=30.0,
                reasoning="No síntomas neurológicos"
            )
        ]

    @pytest.mark.asyncio
    async def test_consensus_initialization(self, mock_llm_service):
        """Test inicialización de consenso."""
        agent = ConsensusAgent(llm_service=mock_llm_service)
        assert agent.llm == mock_llm_service

    @pytest.mark.asyncio
    async def test_select_specialist_high_relevance(self, sample_evaluations):
        """Test selección con alta relevancia."""
        agent = ConsensusAgent()

        decision = await agent.select_specialist(sample_evaluations)

        assert "selected_specialist" in decision
        assert decision["selected_specialist"] == "cardiologia"
        assert decision["confidence"] >= 0.8

    @pytest.mark.asyncio
    async def test_select_specialist_low_relevance(self):
        """Test selección con baja relevancia (default a medicina general)."""
        agent = ConsensusAgent()

        low_evaluations = [
            SpecialistEvaluation(
                specialist_type="cardiologia",
                relevance_score=20.0,
                reasoning="No aplica"
            ),
            SpecialistEvaluation(
                specialist_type="neurologia",
                relevance_score=15.0,
                reasoning="No aplica"
            )
        ]

        decision = await agent.select_specialist(low_evaluations)

        assert decision["selected_specialist"] == "medicina_general"

    @pytest.mark.asyncio
    async def test_select_specialist_empty(self):
        """Test selección sin evaluaciones."""
        agent = ConsensusAgent()

        decision = await agent.select_specialist([])

        assert "selected_specialist" in decision
        assert "error" in decision


class TestAgentFactory:
    """Tests para AgentFactory."""

    def test_create_agent_valid_specialty(self):
        """Test creación de agente válido."""
        agent = AgentFactory.create_agent("cardiologia")

        assert agent is not None
        assert isinstance(agent, BaseMedicalAgent)
        assert agent.specialty == "cardiologia"

    def test_create_agent_invalid_specialty(self):
        """Test creación con especialidad inválida."""
        agent = AgentFactory.create_agent("especialidad_inexistente")

        assert agent is None

    def test_create_all_specialists(self):
        """Test creación de todos los especialistas."""
        agents = AgentFactory.create_all_specialists()

        assert len(agents) == 8

        specialties = [agent.specialty for agent in agents]
        assert "cardiologia" in specialties
        assert "neurologia" in specialties
        assert "medicina_general" in specialties

    def test_get_available_specialties(self):
        """Test obtención de especialidades disponibles."""
        specialties = AgentFactory.get_available_specialties()

        assert isinstance(specialties, list)
        assert len(specialties) == 8
        assert "cardiologia" in specialties

    def test_validate_specialty(self):
        """Test validación de especialidad."""
        assert AgentFactory.validate_specialty("cardiologia") is True
        assert AgentFactory.validate_specialty("medicina_general") is True
        assert AgentFactory.validate_specialty("inexistente") is False

