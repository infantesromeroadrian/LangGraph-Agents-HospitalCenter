"""Agente especialista en Traumatología y Ortopedia."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class OrthopedicsAgent(BaseMedicalAgent):
    """Agente especializado en Traumatología y Ortopedia."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de traumatología y ortopedia.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="traumatologia", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para traumatología."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("traumatologia")

    def _get_evaluation_criteria(self) -> list:
        """
        Retorna criterios de evaluación para traumatología.

        Returns:
            Lista de criterios ortopédicos
        """
        return [
            "Fracturas óseas",
            "Esguinces y luxaciones",
            "Dolor articular (rodilla, cadera, hombro)",
            "Lesiones deportivas",
            "Problemas de columna vertebral",
            "Hernias discales",
            "Artrosis y artritis",
            "Lesiones de ligamentos",
            "Tendinitis y bursitis",
            "Deformidades óseas",
        ]
