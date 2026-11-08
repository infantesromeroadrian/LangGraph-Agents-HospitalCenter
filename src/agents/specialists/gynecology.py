"""Agente especialista en Ginecología."""

import logging

from src.agents.base_agent import BaseMedicalAgent
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class GynecologyAgent(BaseMedicalAgent):
    """Agente especializado en Ginecología."""

    def __init__(self, llm_service: LLMService | None = None):
        """Inicializa el agente de ginecología."""
        super().__init__(specialty="ginecologia", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """Retorna el prompt de sistema para ginecología."""
        from src.config.prompts import get_specialty_prompt

        return get_specialty_prompt("ginecologia")
