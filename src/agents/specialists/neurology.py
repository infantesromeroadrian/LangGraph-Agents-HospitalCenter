"""Agente especialista en Neurología."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class NeurologyAgent(BaseMedicalAgent):
    """Agente especializado en Neurología."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de neurología.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="neurologia", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para neurología."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("neurologia")

    def _get_evaluation_criteria(self) -> list:
        """
        Retorna criterios de evaluación para neurología.

        Returns:
            Lista de criterios neurológicos
        """
        return [
            "Cefaleas y migrañas",
            "Mareos y vértigo",
            "Pérdida de conciencia o desmayos",
            "Convulsiones o epilepsia",
            "Problemas de memoria o cognitivos",
            "Trastornos del movimiento (temblores, Parkinson)",
            "Accidente cerebrovascular (ACV)",
            "Esclerosis múltiple",
            "Neuropatías periféricas",
            "Alteraciones del sueño neurológicas",
        ]
