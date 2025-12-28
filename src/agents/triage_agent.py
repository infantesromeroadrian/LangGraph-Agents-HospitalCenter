"""Agente de triaje médico inicial."""

import logging
from typing import Optional
from uuid import UUID

from src.agents.base_agent import BaseMedicalAgent
from src.config.prompts import TRIAGE_PROMPT, get_all_specialties
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class TriageAgent(BaseMedicalAgent):
    """Agente especializado en triaje médico inicial."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de triaje.

        Args:
            llm_service: Servicio LLM opcional
        """
        # IMPORTANTE: Definir available_specialties ANTES de super().__init__()
        # porque _get_system_prompt() se llama durante la inicialización del padre
        self.available_specialties = get_all_specialties()
        super().__init__(specialty="Triaje", llm_service=llm_service)

    def _get_system_prompt(self) -> str:
        """
        Obtiene el prompt de sistema para triaje.

        Returns:
            Prompt de sistema
        """
        return f"""Eres un médico de triaje experto en evaluación inicial de pacientes.

Tu misión es analizar rápidamente la consulta del paciente y determinar:
1. Nivel de urgencia (urgente, no_urgente, consulta_general)
2. Síntomas principales identificados
3. Especialidades médicas más apropiadas
4. Información adicional que sería útil conocer

Especialidades disponibles en el sistema:
{", ".join(self.available_specialties)}

IMPORTANTE:
- Sé preciso y objetivo en tu evaluación
- Identifica claramente los síntomas mencionados
- Recomienda 1-3 especialidades según relevancia
- Si hay señales de emergencia, marca como "urgente"
"""

    async def evaluate(
        self, message, session_id: Optional[UUID] = None, patient_context: Optional[str] = None
    ) -> dict:
        """
        Analiza la consulta inicial del paciente.

        Args:
            message: Mensaje del paciente (str o Message object)
            session_id: ID de la sesión
            patient_context: ✅ NUEVO - Contexto del paciente (alergias, medicación, antecedentes)

        Returns:
            Análisis de triaje estructurado
        """
        try:
            # Extraer contenido del mensaje
            patient_query = message.content if hasattr(message, "content") else str(message)

            logger.info(f"ℹ️ Triaje: Analizando consulta (sesión={session_id})")

            # ✅ NUEVO: Inyectar contexto del paciente en el prompt
            user_prompt = TRIAGE_PROMPT.format(patient_query=patient_query)

            if patient_context:
                user_prompt = f"{patient_context}\n\n---\n\n{user_prompt}"
                logger.info("✅ Triaje: Contexto del paciente INYECTADO en el prompt")

            # Construir mensajes
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Solicitar análisis en JSON
            analysis = await self.llm.complete_json(messages)

            # Validar estructura básica
            self._validate_analysis(analysis)

            # Añadir metadata
            analysis["session_id"] = str(session_id) if session_id else None
            analysis["query_length"] = len(patient_query)

            # Crear resumen para el usuario
            urgency_text = {
                "urgente": "⚠️ URGENTE",
                "no_urgente": "ℹ️ No urgente",
                "consulta_general": "💬 Consulta general",
            }.get(analysis.get("urgency", "consulta_general"), "💬 Consulta general")

            analysis["summary"] = (
                f"{urgency_text}\n\n"
                f"He analizado tu consulta y voy a derivarla a nuestros especialistas para una evaluación detallada."
            )

            logger.info(
                f"ℹ️ Triaje: Análisis completado "
                f"(urgencia={analysis.get('urgency', 'N/A')}, "
                f"especialidades={len(analysis.get('recommended_specialties', []))})"
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ Triaje: Error en análisis: {e!s}")

            # Retornar análisis por defecto en caso de error
            return self._get_default_analysis(patient_query)

    def _validate_analysis(self, analysis: dict):
        """
        Valida que el análisis tenga la estructura esperada.

        Args:
            analysis: Análisis a validar

        Raises:
            ValueError: Si falta información crítica
        """
        required_fields = ["urgency", "main_symptoms", "recommended_specialties", "reasoning"]

        missing_fields = [field for field in required_fields if field not in analysis]

        if missing_fields:
            logger.warning(f"⚠️ Triaje: Campos faltantes en análisis: {missing_fields}")

            # Completar con valores por defecto
            if "urgency" not in analysis:
                analysis["urgency"] = "consulta_general"
            if "main_symptoms" not in analysis:
                analysis["main_symptoms"] = []
            if "recommended_specialties" not in analysis:
                analysis["recommended_specialties"] = ["medicina_general"]
            if "reasoning" not in analysis:
                analysis["reasoning"] = "Análisis incompleto"

    def _get_default_analysis(self, query: str) -> dict:
        """
        Obtiene un análisis por defecto en caso de error.

        Args:
            query: Consulta original

        Returns:
            Análisis por defecto
        """
        return {
            "urgency": "consulta_general",
            "main_symptoms": ["síntomas no especificados"],
            "recommended_specialties": ["medicina_general"],
            "reasoning": "Análisis por defecto debido a error en procesamiento",
            "additional_info_needed": [
                "Descripción más detallada de los síntomas",
                "Tiempo de evolución de los síntomas",
            ],
            "error": True,
        }

    def is_urgent(self, analysis: dict) -> bool:
        """
        Determina si el caso es urgente según el análisis.

        Args:
            analysis: Análisis de triaje

        Returns:
            True si es urgente
        """
        return analysis.get("urgency", "").lower() == "urgente"

    def get_top_specialties(self, analysis: dict, top_n: int = 3) -> list[str]:
        """
        Obtiene las especialidades más recomendadas.

        Args:
            analysis: Análisis de triaje
            top_n: Número de especialidades a retornar

        Returns:
            Lista de especialidades recomendadas
        """
        specialties = analysis.get("recommended_specialties", [])
        return specialties[:top_n]
