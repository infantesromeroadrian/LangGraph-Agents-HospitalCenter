"""Agente especialista en Cardiología."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class CardiologyAgent(BaseMedicalAgent):
    """Agente especializado en Cardiología."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de cardiología.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="cardiologia", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para cardiología."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("cardiologia")

    def _get_evaluation_criteria(self) -> list:
        """
        Retorna criterios de evaluación para cardiología.

        Returns:
            Lista de criterios cardíacos
        """
        return [
            "Dolor torácico",
            "Palpitaciones o arritmias",
            "Falta de aire (disnea)",
            "Hipertensión arterial",
            "Infarto agudo de miocardio",
            "Insuficiencia cardíaca",
            "Problemas de circulación",
            "Factores de riesgo cardiovascular",
            "Edema en extremidades",
        ]
