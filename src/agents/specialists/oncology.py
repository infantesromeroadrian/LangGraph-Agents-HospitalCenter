"""Agente especialista en Oncología."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class OncologyAgent(BaseMedicalAgent):
    """Agente especializado en Oncología."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de oncología.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="oncologia", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para oncología."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("oncologia")

    def _get_evaluation_criteria(self) -> list:
        """
        Retorna criterios de evaluación para oncología.

        Returns:
            Lista de criterios oncológicos
        """
        return [
            "Sospecha de cáncer o tumor",
            "Pérdida de peso inexplicable",
            "Síntomas B (fiebre, sudores nocturnos, pérdida de peso)",
            "Nódulos o masas palpables",
            "Sangrado anormal",
            "Cambios en lunares (melanoma)",
            "Fatiga extrema persistente",
            "Antecedentes familiares de cáncer",
            "Seguimiento de tratamiento oncológico",
            "Dolor persistente sin causa clara",
        ]
