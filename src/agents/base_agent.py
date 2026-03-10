"""Clase base abstracta para agentes médicos."""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional
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
        from src.config.prompts import get_specialty_protocol

        # Fix: import the global llm_service properly
        from src.services.llm_service import llm_service as global_llm_service

        self.llm = llm_service if llm_service is not None else global_llm_service
        self.specialty_protocol = get_specialty_protocol(self.specialty)
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
    ) -> SpecialistEvaluation | dict[str, Any]:
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
            raw_query = query

            logger.debug(f"🐞 {self.specialty}: Evaluando caso")

            # ✅ NUEVO: Inyectar contexto del paciente SI está disponible
            if patient_context:
                query = f"{patient_context}\n\n---\n\nCONSULTA DEL PACIENTE:\n{query}"
                logger.debug(f"✅ {self.specialty}: Contexto del paciente INYECTADO")

            # Construir mensajes para evaluación
            messages = [
                {"role": "system", "content": self.system_prompt},
                self._build_llm_user_message(
                    self._format_evaluation_prompt(query, triage_analysis or {}), message
                ),
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
            evaluation = self._apply_specialty_relevance_heuristics(raw_query, evaluation)

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
        message: str | Message,
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
            history_for_turn = self._prepare_history_for_current_turn(message, history)

            # Construir mensajes para chat
            session_context = self._build_session_context(message, session_id, history_for_turn)

            if session_context["consultation_stage"] == "appointment_request":
                return self._build_appointment_guidance(message, history_for_turn, session_context)

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "system", "content": self._get_chat_prompt(session_context)},
            ]

            # ✅ NUEVO: Inyectar contexto del paciente ANTES del historial
            if patient_context:
                messages.append({"role": "system", "content": patient_context})
                logger.info(f"✅ {self.specialty}: Contexto del paciente INYECTADO en el chat")

            # Añadir historial de conversación
            for msg in history_for_turn[-10:]:  # Últimos 10 mensajes
                messages.append(msg.to_langchain_format())

            # Añadir mensaje actual
            messages.append(
                self._build_llm_user_message(self._extract_message_text(message), message)
            )

            # Generar respuesta
            response = await self.llm.complete(messages)

            logger.info(f"ℹ️ {self.specialty}: Respuesta generada")

            return response

        except Exception as e:
            logger.error(f"❌ {self.specialty}: Error en chat: {e!s}")
            return "Disculpa, he tenido un problema técnico. ¿Podrías reformular tu pregunta?"

    def _prepare_history_for_current_turn(
        self, current_message: str | Message, history: list[Message]
    ) -> list[Message]:
        """Evita duplicar el mensaje actual cuando ya viene dentro del estado."""
        current_text = self._extract_message_text(current_message).strip()
        if history and history[-1].role == "user" and history[-1].content.strip() == current_text:
            return history[:-1]
        return history

    def _extract_message_text(self, message: str | Message) -> str:
        """Extrae el texto del mensaje actual."""
        return message.content if isinstance(message, Message) else message

    def _build_llm_user_message(
        self, prompt_text: str, raw_message: str | Message
    ) -> dict[str, Any]:
        """Construye un mensaje user multimodal si hay imágenes adjuntas."""
        attachments = (
            raw_message.get_image_attachments() if isinstance(raw_message, Message) else []
        )
        if not attachments:
            return {"role": "user", "content": prompt_text}

        content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        for attachment in attachments:
            content_parts.append(
                {"type": "image_url", "image_url": {"url": attachment["data_url"]}}
            )
        return {"role": "user", "content": content_parts}

    def _build_session_context(
        self, current_message: str | Message, session_id: UUID, history: list[Message]
    ) -> dict[str, Any]:
        """Construye contexto clínico y de etapa conversacional."""
        current_text = self._extract_message_text(current_message)
        has_previous_specialist_turn = any(
            msg.role == "assistant" and msg.specialist_type == self.specialty for msg in history
        )
        appointment_intent = self._detect_appointment_intent(current_text)

        session_context: dict[str, Any] = {
            "session_id": str(session_id),
            "specialty": self.specialty,
            "history_messages": len(history),
            "appointment_intent": appointment_intent,
            "specialty_focus": self.specialty_protocol.get("focus", "valoración clínica general"),
            "required_clinical_topics": self.specialty_protocol.get("required_topics", []),
            "red_flag_topics": self.specialty_protocol.get("red_flags", []),
            "has_image_attachments": isinstance(current_message, Message)
            and current_message.has_image_attachments(),
            "image_attachment_count": len(current_message.get_image_attachments())
            if isinstance(current_message, Message)
            else 0,
        }

        checklist_state = self._assess_specialty_checklist(current_text, history)
        missing_keys = [key for key, present in checklist_state.items() if not present]
        missing_labels = [
            self._get_specialty_checklist_labels().get(key, key.replace("_", " "))
            for key in missing_keys
        ]

        if appointment_intent:
            stage = "appointment_request"
        elif not has_previous_specialist_turn:
            stage = "initial_interview"
        elif missing_keys:
            stage = "targeted_follow_up"
        else:
            stage = "assessment_ready"

        session_context.update(
            {
                "consultation_stage": stage,
                "clinical_checklist": checklist_state,
                "missing_clinical_item_keys": missing_keys,
                "missing_clinical_items": missing_labels,
                "can_close_assessment": not missing_keys,
            }
        )
        return session_context

    def _detect_appointment_intent(self, message: str) -> bool:
        """Detecta si el usuario está pidiendo una cita."""
        normalized = message.lower()
        patterns = [
            r"\bquiero (una )?cita\b",
            r"\bpedir (una )?cita\b",
            r"\bprogram(ar|a) (una )?cita\b",
            r"\bagend(ar|a)\b",
            r"\breserv(ar|a) (una )?cita\b",
            r"\bsolicitar (una )?cita\b",
        ]
        return any(re.search(pattern, normalized) for pattern in patterns)

    def _apply_specialty_relevance_heuristics(
        self, query: str, evaluation: SpecialistEvaluation
    ) -> SpecialistEvaluation:
        """Ajusta relevancia en casos anatómicamente muy característicos."""
        normalized = query.lower()
        gynecology_signals = [
            r"vagina",
            r"vaginal",
            r"vulva",
            r"flujo",
            r"candidiasis",
            r"vaginosis",
            r"secreci[oó]n vaginal",
            r"picor vaginal",
            r"prurito vaginal",
        ]
        has_gynecology_signal = self._contains_any(normalized, gynecology_signals)

        if has_gynecology_signal and self.specialty == "ginecologia":
            evaluation.relevance_score = max(evaluation.relevance_score, 88.0)
            evaluation.confidence = max(evaluation.confidence, 0.85)

        if has_gynecology_signal and self.specialty == "dermatologia":
            evaluation.relevance_score = min(evaluation.relevance_score, 55.0)
            evaluation.confidence = min(evaluation.confidence, 0.6)

        return evaluation

    def _assess_specialty_checklist(
        self, current_message: str, history: list[Message]
    ) -> dict[str, bool]:
        """Evalúa si ya se obtuvo la información mínima para la especialidad actual."""
        user_text = " ".join(
            [msg.content for msg in history if msg.role == "user"] + [current_message]
        ).lower()

        checklist_state: dict[str, bool] = {}
        for item in self.specialty_protocol.get("checklist_items", []):
            checklist_state[item["key"]] = self._contains_any(user_text, item.get("patterns", []))
        return checklist_state

    def _get_specialty_checklist_labels(self) -> dict[str, str]:
        """Retorna etiquetas legibles de la checklist clínica."""
        return {
            item["key"]: item.get("label", item["key"].replace("_", " "))
            for item in self.specialty_protocol.get("checklist_items", [])
        }

    def _contains_any(self, text: str, patterns: list[str]) -> bool:
        """Evalúa si el texto contiene alguno de los patrones."""
        return any(re.search(pattern, text) for pattern in patterns)

    def _build_appointment_guidance(
        self,
        current_message: str | Message,
        history: list[Message],
        session_context: dict[str, Any],
    ) -> str:
        """Genera una respuesta honesta cuando el usuario pide cita sin integración real."""
        current_text = self._extract_message_text(current_message)
        summary = self._build_recent_user_summary(current_text, history)
        missing_items = session_context.get("missing_clinical_items", [])
        urgency_line = self._get_appointment_urgency_guidance(history, current_text)

        response_parts = [
            "Puedo orientarte con la cita, pero este chat no puede reservarla directamente.",
            urgency_line,
            "Resumen para pedir la cita:",
            f"- Especialidad recomendada: {self.specialty.replace('_', ' ').title()}",
            f"- Motivo resumido: {summary}",
        ]

        if missing_items:
            response_parts.extend(
                [
                    "Antes de pedirla, aún faltan datos clínicos importantes que conviene comentar en la consulta:",
                    f"- {', '.join(item.replace('_', ' ') for item in missing_items)}",
                ]
            )

        response_parts.extend(
            [
                "Qué puedes hacer ahora:",
                "1. Solicita una cita presencial con la especialidad recomendada.",
                "2. Al pedirla, comenta el resumen anterior tal como aparece.",
                "3. Si presentas fiebre, dolor intenso, mal olor muy fuerte, sangrado anormal o empeoramiento rápido, acude a urgencias.",
            ]
        )

        return "\n\n".join(response_parts)

    def _build_recent_user_summary(self, current_message: str, history: list[Message]) -> str:
        """Resume de forma compacta lo último que ha contado el paciente."""
        recent_user_messages = [msg.content.strip() for msg in history if msg.role == "user"]
        recent_user_messages.append(current_message.strip())
        summary = "; ".join(msg for msg in recent_user_messages[-3:] if msg)
        return summary[:320] + ("..." if len(summary) > 320 else "")

    def _get_appointment_urgency_guidance(
        self, history: list[Message], current_message: str
    ) -> str:
        """Devuelve una recomendación temporal para la cita según contexto clínico."""
        user_text = " ".join(
            [msg.content for msg in history if msg.role == "user"] + [current_message]
        ).lower()
        if self._contains_any(
            user_text, [r"fiebre", r"sangrad", r"dolor intenso", r"dolor severo"]
        ):
            return "Por los síntomas descritos, si alguno de esos signos es intenso o actual, la valoración debe ser hoy mismo en urgencias."
        if self.specialty == "ginecologia":
            return "Con la información disponible, lo razonable es una valoración presencial de ginecología en 24-72 horas, antes si empeora."
        return "Con la información disponible, conviene una valoración presencial en los próximos días."

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
            session_context=json.dumps(session_context, ensure_ascii=False, indent=2),
        )

    def get_specialty_info(self) -> dict:
        """
        Obtiene información sobre la especialidad.

        Returns:
            Información del especialista
        """
        return {"specialty": self.specialty, "system_prompt_length": len(self.system_prompt)}
