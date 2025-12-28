"""Clase base abstracta para agentes médicos."""

import logging
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.models.evaluation import SpecialistEvaluation
from src.models.message import Message
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class BaseMedicalAgent(ABC):
    """Clase base abstracta para todos los agentes médicos especializados."""

    def __init__(self, specialty: str, llm_service: Optional[LLMService] = None):
        """
        Inicializa un agente médico.

        Args:
            specialty: Nombre de la especialidad médica
            llm_service: Servicio LLM (usa global si no se provee)
        """
        self.specialty = specialty
        # Fix: import the global llm_service properly
        from src.services.llm_service import llm_service as global_llm_service

        self.llm = llm_service if llm_service is not None else global_llm_service
        self.system_prompt = self._get_system_prompt()

        logger.info(f"ℹ️ Agente {self.specialty} inicializado")

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """
        Obtiene el prompt de sistema específico del especialista.

        Returns:
            Prompt de sistema personalizado
        """
        pass

    async def evaluate(
        self,
        message,
        triage_analysis: Optional[dict] = None,
        session_id: Optional[UUID] = None,
        patient_context: Optional[str] = None,  # ✅ NUEVO
    ) -> SpecialistEvaluation:
        """
        Evalúa si un caso pertenece a esta especialidad.

        Args:
            message: Mensaje del paciente (str o Message object)
            triage_analysis: Análisis previo del triaje (opcional)
            session_id: ID de la sesión
            patient_context: ✅ NUEVO - Contexto del paciente (alergias, medicación, antecedentes)

        Returns:
            Evaluación del especialista
        """
        try:
            # Extraer contenido del mensaje
            query = message.content if hasattr(message, "content") else str(message)

            logger.debug(f"🐞 {self.specialty}: Evaluando caso")

            # ✅ NUEVO: Inyectar contexto del paciente SI está disponible
            if patient_context:
                query = f"{patient_context}\n\n---\n\nCONSULTA DEL PACIENTE:\n{query}"
                logger.debug(f"✅ {self.specialty}: Contexto del paciente INYECTADO")

            # Construir mensajes para evaluación
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": self._format_evaluation_prompt(query, triage_analysis or {}),
                },
            ]

            # Solicitar evaluación en JSON
            response = await self.llm.complete_json(messages)

            # Crear objeto de evaluación
            evaluation = SpecialistEvaluation(
                specialist_type=self.specialty,
                relevance_score=float(response.get("relevance_score", 0)),
                reasoning=response.get("reasoning", ""),
                session_id=session_id,
                confidence=float(response.get("confidence", 0.5)),
                key_symptoms=response.get("key_symptoms", []),
                recommended_actions=response.get("recommended_actions", []),
                evaluation_data=response,
            )

            logger.info(
                f"ℹ️ {self.specialty}: Evaluación completada "
                f"(relevancia={evaluation.relevance_score:.1f})"
            )

            return evaluation

        except Exception as e:
            logger.error(f"❌ {self.specialty}: Error en evaluación: {e!s}")

            # Retornar evaluación por defecto en caso de error
            return SpecialistEvaluation(
                specialist_type=self.specialty,
                relevance_score=0.0,
                reasoning=f"Error en evaluación: {e!s}",
                session_id=session_id,
            )

    async def chat(
        self,
        message: str,
        session_id,
        history: list[Message],
        patient_context: Optional[str] = None,
    ) -> str:
        """
        Mantiene conversación con el paciente como especialista.

        Args:
            message: Mensaje del paciente
            session_id: ID de la sesión
            history: Historial de conversación
            patient_context: ✅ NUEVO - Contexto del paciente (alergias, medicación, antecedentes)

        Returns:
            Respuesta del especialista
        """
        try:
            logger.debug(f"🐞 {self.specialty}: Generando respuesta")

            # Construir mensajes para chat
            session_context = {"session_id": str(session_id)}
            messages = [{"role": "system", "content": self._get_chat_prompt(session_context)}]

            # ✅ NUEVO: Inyectar contexto del paciente ANTES del historial
            if patient_context:
                messages.append({"role": "system", "content": patient_context})
                logger.info(f"✅ {self.specialty}: Contexto del paciente INYECTADO en el chat")

            # Añadir historial de conversación
            for msg in history[-10:]:  # Últimos 10 mensajes
                messages.append({"role": msg.role, "content": msg.content})

            # Añadir mensaje actual
            messages.append({"role": "user", "content": message})

            # Generar respuesta
            response = await self.llm.complete(messages)

            logger.info(f"ℹ️ {self.specialty}: Respuesta generada")

            return response

        except Exception as e:
            logger.error(f"❌ {self.specialty}: Error en chat: {e!s}")
            return "Disculpa, he tenido un problema técnico. ¿Podrías reformular tu pregunta?"

    def _format_evaluation_prompt(self, query: str, triage_analysis: dict) -> str:
        """
        Formatea el prompt de evaluación.

        Args:
            query: Consulta del paciente
            triage_analysis: Análisis de triaje

        Returns:
            Prompt formateado
        """
        from src.config.prompts import SPECIALIST_EVALUATION_PROMPT

        return SPECIALIST_EVALUATION_PROMPT.format(
            specialty=self.specialty, triage_analysis=str(triage_analysis), patient_query=query
        )

    def _get_chat_prompt(self, session_context: dict) -> str:
        """
        Obtiene el prompt para conversación.

        Args:
            session_context: Contexto de la sesión

        Returns:
            Prompt de chat
        """
        from src.config.prompts import SPECIALIST_CHAT_PROMPT

        return SPECIALIST_CHAT_PROMPT.format(
            specialty=self.specialty,
            session_context=str(session_context),
            conversation_history="{conversation_history}",
            patient_message="{patient_message}",
        ).split("{conversation_history}")[0]

    def get_specialty_info(self) -> dict:
        """
        Obtiene información sobre la especialidad.

        Returns:
            Información del especialista
        """
        return {"specialty": self.specialty, "system_prompt_length": len(self.system_prompt)}
