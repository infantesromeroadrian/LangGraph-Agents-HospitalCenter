"""Agente especialista en Pediatría."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class PediatricsAgent(BaseMedicalAgent):
    """Agente especializado en Pediatría."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de pediatría.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="pediatria", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para pediatría."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("pediatria")

    def _get_evaluation_criteria(self) -> list:
        """
        Retorna criterios de evaluación para pediatría.

        Returns:
            Lista de criterios pediátricos
        """
        return [
            "Paciente menor de 18 años",
            "Enfermedades infantiles comunes",
            "Desarrollo y crecimiento",
            "Vacunación y prevención",
            "Fiebre en niños",
            "Problemas de alimentación",
            "Trastornos del desarrollo",
            "Infecciones respiratorias pediátricas",
            "Alergias infantiles",
            "Control de niño sano",
        ]
