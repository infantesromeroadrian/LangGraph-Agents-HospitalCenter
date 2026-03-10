"""Servicio para interactuar con el modelo LLM configurado."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Optional

from openai import AsyncOpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Servicio para interactuar con modelos de OpenAI."""

    def __init__(self):
        """Inicializa el servicio LLM."""
        self.base_url = settings.OPENAI_BASE_URL.rstrip("/")
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=self.base_url,
            timeout=settings.OPENAI_TIMEOUT,
        )
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.is_groq_compatible = "api.groq.com" in self.base_url

        logger.info(f"ℹ️ LLMService inicializado con modelo: {self.model}")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def complete(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        Genera una respuesta del LLM.

        Args:
            messages: Lista de mensajes en formato OpenAI
            temperature: Temperatura para la generación (override)
            max_tokens: Máximo de tokens (override)
            response_format: Formato de respuesta (ej: {"type": "json_object"})

        Returns:
            Respuesta del LLM como string
        """
        try:
            logger.debug(f"🐞 Llamando a LLM con {len(messages)} mensajes")

            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature or self.temperature,
            }

            token_limit = max_tokens or self.max_tokens
            if self.is_groq_compatible:
                params["max_tokens"] = token_limit
            else:
                params["max_completion_tokens"] = token_limit

            if response_format:
                params["response_format"] = response_format

            response = await self.client.chat.completions.create(**params)

            content = response.choices[0].message.content

            logger.info(f"ℹ️ LLM respondió con {len(content)} caracteres")

            return content

        except OpenAIError as e:
            logger.error(f"❌ Error en LLM: {e!s}")
            raise
        except Exception as e:
            logger.error(f"❌ Error inesperado en LLM: {e!s}")
            raise

    async def complete_json(
        self, messages: list[dict], temperature: Optional[float] = None
    ) -> dict:
        """
        Genera una respuesta en formato JSON.

        Args:
            messages: Lista de mensajes
            temperature: Temperatura para la generación

        Returns:
            Respuesta parseada como diccionario
        """
        response = ""
        try:
            response = await self.complete(
                messages=messages, temperature=temperature, response_format={"type": "json_object"}
            )

            return json.loads(response)

        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON: {e!s}")
            logger.debug(f"🐞 Respuesta recibida: {response}")
            raise ValueError(f"LLM no retornó JSON válido: {e!s}") from e

    async def stream_complete(
        self, messages: list[dict], temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """
        Genera respuesta con streaming.

        Args:
            messages: Lista de mensajes
            temperature: Temperatura para la generación

        Yields:
            Chunks de texto de la respuesta
        """
        try:
            logger.debug(f"🐞 Iniciando streaming con {len(messages)} mensajes")

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

            logger.info("ℹ️ Streaming completado")

        except OpenAIError as e:
            logger.error(f"❌ Error en streaming: {e!s}")
            raise
        except Exception as e:
            logger.error(f"❌ Error inesperado en streaming: {e!s}")
            raise

    def create_message(self, role: str, content: str) -> dict:
        """
        Crea un mensaje en formato OpenAI.

        Args:
            role: Rol del mensaje (system, user, assistant)
            content: Contenido del mensaje

        Returns:
            Mensaje en formato OpenAI
        """
        return {"role": role, "content": content}

    def format_conversation_history(self, messages: list) -> list[dict]:
        """
        Formatea historial de conversación para OpenAI.

        Args:
            messages: Lista de objetos Message

        Returns:
            Lista de mensajes en formato OpenAI
        """
        return [{"role": msg.role, "content": msg.content} for msg in messages]


# Instancia global del servicio
llm_service = LLMService()
