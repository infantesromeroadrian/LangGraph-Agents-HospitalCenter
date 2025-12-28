"""Agente especialista en Dermatología."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class DermatologyAgent(BaseMedicalAgent):
    """Agente especializado en Dermatología."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de dermatología.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="dermatologia", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para dermatología."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("dermatologia")

    def _get_evaluation_criteria(self) -> list:
        """
        Retorna criterios de evaluación para dermatología.

        Returns:
            Lista de criterios dermatológicos
        """
        return [
            "Lesiones cutáneas o erupciones",
            "Acné y problemas de piel grasa",
            "Eccemas y dermatitis",
            "Psoriasis",
            "Infecciones de piel (hongos, bacterias)",
            "Lunares y lesiones pigmentadas",
            "Cáncer de piel o melanoma",
            "Alopecia o caída del cabello",
            "Problemas de uñas",
            "Alergias cutáneas",
        ]
