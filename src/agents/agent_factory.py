"""Factory para crear agentes médicos."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.agents.specialists import (
    CardiologyAgent,
    DermatologyAgent,
    GeneralMedicineAgent,
    NeurologyAgent,
    OncologyAgent,
    OrthopedicsAgent,
    PediatricsAgent,
    PsychiatryAgent,
)
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory para crear instancias de agentes médicos."""

    # Mapeo de especialidades a clases de agentes
    AGENT_MAP = {
        "medicina_general": GeneralMedicineAgent,
        "cardiologia": CardiologyAgent,
        "neurologia": NeurologyAgent,
        "pediatria": PediatricsAgent,
        "dermatologia": DermatologyAgent,
        "traumatologia": OrthopedicsAgent,
        "psiquiatria": PsychiatryAgent,
        "oncologia": OncologyAgent,
    }

    @classmethod
    def create_agent(
        cls, specialty: str, llm_service: Optional[LLMService] = None
    ) -> Optional[BaseMedicalAgent]:
        """
        Crea un agente médico específico.

        Args:
            specialty: Nombre de la especialidad
            llm_service: Servicio LLM opcional

        Returns:
            Instancia del agente o None si la especialidad no existe
        """
        agent_class = cls.AGENT_MAP.get(specialty.lower())

        if agent_class is None:
            logger.error(f"❌ Especialidad no encontrada: {specialty}")
            return None

        try:
            agent = agent_class(llm_service=llm_service)
            logger.info(f"ℹ️ Agente creado: {specialty}")
            return agent
        except Exception as e:
            logger.error(f"❌ Error creando agente {specialty}: {e!s}")
            return None

    @classmethod
    def create_all_specialists(
        cls, llm_service: Optional[LLMService] = None
    ) -> list[BaseMedicalAgent]:
        """
        Crea todos los agentes especialistas disponibles.

        Args:
            llm_service: Servicio LLM opcional

        Returns:
            Lista de todos los agentes especialistas
        """
        agents = []

        for specialty in cls.AGENT_MAP:
            agent = cls.create_agent(specialty, llm_service)
            if agent:
                agents.append(agent)

        logger.info(f"ℹ️ {len(agents)} agentes especialistas creados")
        return agents

    @classmethod
    def get_available_specialties(cls) -> list[str]:
        """
        Obtiene lista de especialidades disponibles.

        Returns:
            Lista de nombres de especialidades
        """
        return list(cls.AGENT_MAP.keys())

    @classmethod
    def validate_specialty(cls, specialty: str) -> bool:
        """
        Valida si una especialidad existe.

        Args:
            specialty: Nombre de la especialidad

        Returns:
            True si la especialidad existe
        """
        return specialty.lower() in cls.AGENT_MAP
