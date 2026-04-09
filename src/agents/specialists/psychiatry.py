"""Agente especialista en Psiquiatría."""

import logging
from typing import Optional

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class PsychiatryAgent(BaseMedicalAgent):
    """Agente especializado en Psiquiatría."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de psiquiatría.

        Args:
            llm_service: Servicio LLM opcional
        """
        super().__init__(specialty="psiquiatria", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para psiquiatría."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("psiquiatria")
