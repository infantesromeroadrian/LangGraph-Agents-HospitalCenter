"""Tests unitarios para agentes médicos."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from src.agents.agent_factory import AgentFactory
from src.agents.base_agent import BaseMedicalAgent
from src.agents.consensus_agent import ConsensusAgent
from src.agents.specialists.cardiology import CardiologyAgent
from src.agents.specialists.gynecology import GynecologyAgent
from src.agents.triage_agent import TriageAgent
from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message


@pytest.fixture
def mock_llm_service():
    """Mock del servicio LLM."""
    service = AsyncMock()
    service.complete_json = AsyncMock(
        return_value={
            "relevance_score": 75.0,
            "reasoning": "Test reasoning",
            "key_symptoms": ["test symptom"],
            "confidence": 0.8,
            "recommended_actions": ["test action"],
        }
    )
    service.complete = AsyncMock(return_value="Test response")
    return service


@pytest.fixture
def sample_message():
    """Mensaje de prueba."""
    return Message(role="user", content="Tengo dolor en el pecho", session_id=uuid4())


@pytest.fixture
def sample_triage_analysis():
    """Análisis de triaje de prueba."""
    return {
        "urgency": "no_urgente",
        "main_symptoms": ["dolor pecho"],
        "recommended_specialties": ["cardiologia"],
        "reasoning": "Síntomas cardiovasculares",
    }


class TestBaseMedicalAgent:
    """Tests para BaseMedicalAgent."""

    @pytest.mark.parametrize(
        ("specialty", "current_message", "expected_missing"),
        [
            (
                "medicina_general",
                "Tengo fiebre y dolor de garganta desde hace dos días",
                "impacto funcional",
            ),
            (
                "cardiologia",
                "Tengo dolor en el pecho y palpitaciones al subir escaleras",
                "factores de riesgo cardiovascular",
            ),
            (
                "neurologia",
                "Desde ayer tengo dolor de cabeza y hormigueo en el brazo",
                "conciencia, convulsiones o caídas",
            ),
            (
                "pediatria",
                "Mi niño de 3 años tiene fiebre y tos",
                "ingesta, hidratación y diuresis",
            ),
            (
                "dermatologia",
                "Tengo una mancha roja que pica en el brazo",
                "productos o contactos desencadenantes",
            ),
            (
                "traumatologia",
                "Me caí y me duele mucho el tobillo al caminar",
                "inflamación, deformidad o herida",
            ),
            (
                "psiquiatria",
                "Tengo ansiedad desde hace semanas y duermo fatal",
                "riesgo autolesivo o síntomas psicóticos",
            ),
            (
                "ginecologia",
                "Me pica la vagina y tengo flujo amarillo con olor",
                "embarazo, menstruación y relaciones/irritantes",
            ),
            (
                "oncologia",
                "Tengo un bulto en el cuello desde hace dos meses y he perdido peso",
                "dolor e impacto funcional",
            ),
        ],
    )
    def test_specialty_follow_up_stage_requires_missing_data(
        self, mock_llm_service, sample_message, specialty, current_message, expected_missing
    ):
        """Test que todas las especialidades usan follow-up dirigido cuando faltan datos."""
        agent = AgentFactory.create_agent(specialty, llm_service=mock_llm_service)
        assert agent is not None

        history = [
            Message(
                role="assistant",
                content="Necesito hacerte unas preguntas clínicas.",
                session_id=sample_message.session_id,
                specialist_type=specialty,
            )
        ]

        context = agent._build_session_context(
            current_message=current_message,
            session_id=sample_message.session_id,
            history=history,
        )

        assert context["consultation_stage"] == "targeted_follow_up"
        assert context["can_close_assessment"] is False
        assert expected_missing in context["missing_clinical_items"]

    @pytest.mark.parametrize(
        ("specialty", "current_message"),
        [
            (
                "medicina_general",
                "Desde hace cuatro días tengo fiebre y dolor en la garganta, con mucho cansancio; me impide dormir y trabajo, y empezó tras contacto con mi hijo enfermo. Tomo paracetamol y no tengo alergias.",
            ),
            (
                "cardiologia",
                "Desde hace una semana tengo dolor opresivo en el pecho que se va al brazo izquierdo al hacer esfuerzo, con falta de aire, palpitaciones y mareo. Soy hipertenso, fumador y ya tuve un susto cardiaco previo con sudor frío.",
            ),
            (
                "neurologia",
                "Desde ayer tuve un inicio súbito de dolor de cabeza con visión borrosa, hormigueo y debilidad del brazo derecho, me costó hablar y casi me desmayo. Dormí poco y tuve un golpe hace una semana.",
            ),
            (
                "pediatria",
                "Mi niña de 2 años tiene fiebre y vómitos desde hace dos días. Bebe poco, moja menos pañales, está más decaída y respira rápido. Va a guardería y estuvo en contacto con otros niños resfriados; sus vacunas están al día.",
            ),
            (
                "dermatologia",
                "Desde hace una semana tengo una placa roja con costra en la cara que pica y a veces supura. Empezó tras usar una crema nueva, me salió además algo de fiebre y noto irritación en los labios.",
            ),
            (
                "traumatologia",
                "Ayer tuve una caída haciendo deporte y me torcí la rodilla izquierda. Está muy hinchada, con hematoma y algo de deformidad; no puedo apoyar bien, me cuesta doblarla y noto hormigueo hacia la pierna.",
            ),
            (
                "psiquiatria",
                "Desde hace dos meses tengo ansiedad y tristeza casi todos los días. Duermo muy mal, no rindo en el trabajo, he perdido apetito, tomo ansiolíticos de vez en cuando y he llegado a pensar en hacerme daño, aunque sin plan.",
            ),
            (
                "ginecologia",
                "Llevo tres semanas con picor vaginal intermitente, flujo blanco amarillento con mal olor y ardor al orinar, además de dolor pélvico leve. No tengo fiebre ni sangrado, mi última regla fue hace diez días y tuve relaciones; cambié de jabón íntimo.",
            ),
            (
                "oncologia",
                "Desde hace tres meses noto un bulto en la axila que ha crecido, con sangrado ocasional y pérdida de peso. Tengo cansancio, dolor que me impide dormir y antecedentes de quimioterapia por cáncer previo.",
            ),
        ],
    )
    def test_specialty_assessment_ready_when_checklist_complete(
        self, mock_llm_service, sample_message, specialty, current_message
    ):
        """Test que todas las especialidades pueden pasar a assessment_ready con datos suficientes."""
        agent = AgentFactory.create_agent(specialty, llm_service=mock_llm_service)
        assert agent is not None

        history = [
            Message(
                role="assistant",
                content="Necesito hacerte unas preguntas clínicas.",
                session_id=sample_message.session_id,
                specialist_type=specialty,
            )
        ]

        context = agent._build_session_context(
            current_message=current_message,
            session_id=sample_message.session_id,
            history=history,
        )

        assert context["consultation_stage"] == "assessment_ready"
        assert context["can_close_assessment"] is True
        assert context["missing_clinical_items"] == []

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
            message=sample_message,
            triage_analysis=sample_triage_analysis,
            session_id=sample_message.session_id,
            patient_context=None,
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
            session_id=sample_message.session_id,
            history=[sample_message],
            patient_context=None,
        )

        assert isinstance(response, str)
        assert len(response) > 0
        mock_llm_service.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_chat_with_image_attachment(self, mock_llm_service, sample_message):
        """Test conversación multimodal con imagen adjunta."""
        agent = CardiologyAgent(llm_service=mock_llm_service)
        image_message = Message(
            role="user",
            content="Revisa esta imagen del problema",
            session_id=sample_message.session_id,
            metadata={
                "attachments": [
                    {
                        "filename": "photo.jpg",
                        "media_type": "image/jpeg",
                        "data_url": "data:image/jpeg;base64,ZmFrZQ==",
                    }
                ]
            },
        )

        await agent.chat(
            message=image_message,
            session_id=sample_message.session_id,
            history=[image_message],
            patient_context=None,
        )

        sent_messages = mock_llm_service.complete.await_args.args[0]
        assert sent_messages[-1]["role"] == "user"
        assert isinstance(sent_messages[-1]["content"], list)
        assert sent_messages[-1]["content"][1]["type"] == "image_url"

    def test_gynecology_follow_up_stage_requires_more_data(self, mock_llm_service, sample_message):
        """Test que ginecología no cierre si faltan datos clínicos relevantes."""
        agent = GynecologyAgent(llm_service=mock_llm_service)
        history = [
            Message(
                role="assistant",
                content="Necesito hacerte unas preguntas.",
                session_id=sample_message.session_id,
                specialist_type="ginecologia",
            ),
            Message(
                role="user",
                content="Me pica la vagina y tengo flujo amarillo con olor",
                session_id=sample_message.session_id,
            ),
        ]

        context = agent._build_session_context(
            current_message="A veces me duele la pelvis",
            session_id=sample_message.session_id,
            history=history,
        )

        assert context["consultation_stage"] == "targeted_follow_up"
        assert context["can_close_assessment"] is False
        assert "embarazo, menstruación y relaciones/irritantes" in context["missing_clinical_items"]

    @pytest.mark.asyncio
    async def test_gynecology_appointment_request_avoids_fake_booking(
        self, mock_llm_service, sample_message
    ):
        """Test que una petición de cita no simule reserva directa."""
        agent = GynecologyAgent(llm_service=mock_llm_service)
        history = [
            Message(
                role="user",
                content="Me pica la vagina y tengo flujo blanco amarillo con mal olor",
                session_id=sample_message.session_id,
            ),
            Message(
                role="assistant",
                content="Necesito algunas respuestas más.",
                session_id=sample_message.session_id,
                specialist_type="ginecologia",
            ),
        ]

        response = await agent.chat(
            message="Si quiero una cita",
            session_id=sample_message.session_id,
            history=history,
            patient_context=None,
        )

        assert "no puede reservarla directamente" in response.lower()
        assert "resumen para pedir la cita" in response.lower()
        mock_llm_service.complete.assert_not_called()


class TestTriageAgent:
    """Tests para TriageAgent."""

    @pytest.mark.asyncio
    async def test_triage_initialization(self, mock_llm_service):
        """Test inicialización de triaje."""
        agent = TriageAgent(llm_service=mock_llm_service)

        assert agent.specialty == "Triaje"
        assert len(agent.available_specialties) == 9  # Updated: now includes ginecologia

    @pytest.mark.asyncio
    async def test_triage_analyze(self, mock_llm_service, sample_message):
        """Test análisis de triaje."""
        agent = TriageAgent(llm_service=mock_llm_service)

        mock_llm_service.complete_json.return_value = {
            "urgency": "urgente",
            "main_symptoms": ["dolor pecho", "dificultad respirar"],
            "recommended_specialties": ["cardiologia", "medicina_general"],
            "reasoning": "Síntomas cardiovasculares urgentes",
            "additional_info_needed": [],
        }

        # TriageAgent.evaluate() has different signature: (message, session_id, patient_context)
        analysis = await agent.evaluate(
            message="Tengo dolor en el pecho y no puedo respirar bien",
            session_id=sample_message.session_id,
            patient_context=None,
        )

        # evaluate() returns dict for TriageAgent
        assert isinstance(analysis, dict)
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
            "recommended_specialties": [
                "cardiologia",
                "neurologia",
                "medicina_general",
                "pediatria",
            ]
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
                reasoning="Síntomas cardiovasculares claros",
            ),
            SpecialistEvaluation(
                specialist_type="medicina_general",
                relevance_score=70.0,
                reasoning="Consulta general posible",
            ),
            SpecialistEvaluation(
                specialist_type="neurologia",
                relevance_score=30.0,
                reasoning="No síntomas neurológicos",
            ),
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
                specialist_type="cardiologia", relevance_score=20.0, reasoning="No aplica"
            ),
            SpecialistEvaluation(
                specialist_type="neurologia", relevance_score=15.0, reasoning="No aplica"
            ),
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

    def test_create_agent_gynecology(self):
        """Test creación de agente de ginecología."""
        agent = AgentFactory.create_agent("ginecologia")

        assert agent is not None
        assert isinstance(agent, GynecologyAgent)
        assert agent.specialty == "ginecologia"

    def test_create_agent_invalid_specialty(self):
        """Test creación con especialidad inválida."""
        agent = AgentFactory.create_agent("especialidad_inexistente")

        assert agent is None

    def test_create_all_specialists(self):
        """Test creación de todos los especialistas."""
        agents = AgentFactory.create_all_specialists()

        assert len(agents) == 9

        specialties = [agent.specialty for agent in agents]
        assert "cardiologia" in specialties
        assert "neurologia" in specialties
        assert "medicina_general" in specialties
        assert "ginecologia" in specialties

    def test_get_available_specialties(self):
        """Test obtención de especialidades disponibles."""
        specialties = AgentFactory.get_available_specialties()

        assert isinstance(specialties, list)
        assert len(specialties) == 9
        assert "cardiologia" in specialties
        assert "ginecologia" in specialties

    def test_validate_specialty(self):
        """Test validación de especialidad."""
        assert AgentFactory.validate_specialty("cardiologia") is True
        assert AgentFactory.validate_specialty("medicina_general") is True
        assert AgentFactory.validate_specialty("inexistente") is False
