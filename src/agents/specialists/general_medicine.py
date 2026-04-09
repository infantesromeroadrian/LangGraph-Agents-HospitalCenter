"""Agente especialista en Medicina General."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class GeneralMedicineAgent(BaseMedicalAgent):
    """Agente especializado en Medicina General."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de medicina general.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="medicina_general", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para medicina general."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("medicina_general")
