"""Agente de consenso para seleccionar el mejor especialista."""

import logging
from typing import Optional

from src.config.prompts import CONSENSUS_PROMPT
from src.models.evaluation import SpecialistEvaluation
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ConsensusAgent:
    """Agente que decide qué especialista debe atender al paciente."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Inicializa el agente de consenso.

        Args:
            llm_service: Servicio LLM opcional
        """
        from src.services.llm_service import llm_service as global_llm_service

        self.llm = llm_service if llm_service is not None else global_llm_service
        logger.info("ℹ️ ConsensusAgent inicializado")

    async def select_specialist(
        self, evaluations: list[SpecialistEvaluation], voting_weight: str = "balanced"
    ) -> dict:
        """
        Selecciona el mejor especialista basándose en las evaluaciones.

        Args:
            evaluations: Lista de evaluaciones de especialistas
            voting_weight: Estrategia de votación (balanced, weighted, unanimous)

        Returns:
            Decisión de consenso con especialista seleccionado
        """
        try:
            logger.info(f"ℹ️ Consenso: Evaluando {len(evaluations)} especialistas")

            if not evaluations:
                return self._get_default_decision()

            # Ordenar evaluaciones por relevancia
            sorted_evals = sorted(evaluations, key=lambda e: e.relevance_score, reverse=True)

            # Si hay un claro ganador (>= 80), seleccionar directamente
            if sorted_evals[0].relevance_score >= 80:
                return self._create_decision(
                    selected=sorted_evals[0],
                    alternatives=sorted_evals[1:3],
                    reasoning="Especialista claramente indicado por alta relevancia",
                    confidence=0.9,
                )

            # Si todos tienen baja relevancia (< 40), usar medicina general
            if sorted_evals[0].relevance_score < 40:
                return self._get_general_medicine_decision(sorted_evals)

            # Para casos intermedios, usar LLM para decisión más refinada
            return await self._llm_consensus(sorted_evals, voting_weight)

        except Exception as e:
            logger.error(f"❌ Consenso: Error: {e!s}")
            return self._get_default_decision()

    async def _llm_consensus(
        self, evaluations: list[SpecialistEvaluation], _voting_weight: str
    ) -> dict:
        """
        Usa LLM para decisión de consenso refinada.

        Args:
            evaluations: Evaluaciones ordenadas
            voting_weight: Estrategia de votación

        Returns:
            Decisión de consenso
        """
        try:
            # Formatear evaluaciones para el prompt
            eval_text = self._format_evaluations(evaluations)

            # Construir prompt
            prompt = CONSENSUS_PROMPT.format(
                num_specialists=len(evaluations), evaluations=eval_text
            )

            messages = [
                {"role": "system", "content": "Eres un coordinador médico experto en triaje."},
                {"role": "user", "content": prompt},
            ]

            # Solicitar decisión en JSON
            decision = await self.llm.complete_json(messages)

            # Validar y ajustar decisión
            selected_specialist = decision.get("selected_specialist", "")

            # Encontrar la evaluación seleccionada
            selected_eval = next(
                (
                    e
                    for e in evaluations
                    if e.specialist_type.lower() == selected_specialist.lower()
                ),
                evaluations[0],  # Fallback al primero
            )

            alternatives = [
                e.specialist_type
                for e in evaluations
                if e.specialist_type != selected_eval.specialist_type
            ][:2]

            result = {
                "selected_specialist": selected_eval.specialist_type,
                "confidence": float(decision.get("confidence", 0.7)),
                "reasoning": decision.get("reasoning", ""),
                "alternative_specialists": alternatives,
                "urgency_level": decision.get("urgency_level", "media"),
                "evaluation_scores": {e.specialist_type: e.relevance_score for e in evaluations},
            }

            logger.info(
                f"ℹ️ Consenso: {result['selected_specialist']} seleccionado "
                f"(confianza={result['confidence']:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Consenso LLM: Error: {e!s}")
            return self._create_decision(
                selected=evaluations[0],
                alternatives=evaluations[1:3],
                reasoning="Selección por relevancia más alta (error en consenso LLM)",
                confidence=0.6,
            )

    def _format_evaluations(self, evaluations: list[SpecialistEvaluation]) -> str:
        """
        Formatea las evaluaciones para el prompt.

        Args:
            evaluations: Lista de evaluaciones

        Returns:
            Texto formateado
        """
        lines = []
        for i, eval in enumerate(evaluations, 1):
            lines.append(f"{i}. {eval.specialist_type}")
            lines.append(f"   - Relevancia: {eval.relevance_score:.1f}/100")
            lines.append(f"   - Confianza: {eval.confidence:.2f}")
            lines.append(f"   - Razonamiento: {eval.reasoning}")
            if eval.key_symptoms:
                lines.append(f"   - Síntomas clave: {', '.join(eval.key_symptoms)}")
            lines.append("")

        return "\n".join(lines)

    def _create_decision(
        self,
        selected: SpecialistEvaluation,
        alternatives: list[SpecialistEvaluation],
        reasoning: str,
        confidence: float,
    ) -> dict:
        """
        Crea un diccionario de decisión.

        Args:
            selected: Especialista seleccionado
            alternatives: Especialistas alternativos
            reasoning: Razonamiento de la decisión
            confidence: Nivel de confianza

        Returns:
            Decisión estructurada
        """
        return {
            "selected_specialist": selected.specialist_type,
            "confidence": confidence,
            "reasoning": reasoning,
            "alternative_specialists": [e.specialist_type for e in alternatives],
            "urgency_level": self._determine_urgency(selected),
            "evaluation_scores": {selected.specialist_type: selected.relevance_score},
        }

    def _determine_urgency(self, evaluation: SpecialistEvaluation) -> str:
        """
        Determina nivel de urgencia basado en evaluación.

        Args:
            evaluation: Evaluación del especialista

        Returns:
            Nivel de urgencia (alta, media, baja)
        """
        if evaluation.relevance_score >= 85:
            return "alta"
        elif evaluation.relevance_score >= 60:
            return "media"
        else:
            return "baja"

    def _get_general_medicine_decision(self, evaluations: list[SpecialistEvaluation]) -> dict:
        """
        Retorna decisión para medicina general cuando no hay especialista claro.

        Args:
            evaluations: Evaluaciones originales

        Returns:
            Decisión hacia medicina general
        """
        return {
            "selected_specialist": "medicina_general",
            "confidence": 0.5,
            "reasoning": (
                "Ningún especialista mostró relevancia alta. "
                "Recomendando medicina general para evaluación inicial."
            ),
            "alternative_specialists": [e.specialist_type for e in evaluations[:2]],
            "urgency_level": "baja",
            "evaluation_scores": {e.specialist_type: e.relevance_score for e in evaluations},
        }

    def _get_default_decision(self) -> dict:
        """
        Retorna decisión por defecto en caso de error.

        Returns:
            Decisión por defecto
        """
        return {
            "selected_specialist": "medicina_general",
            "confidence": 0.3,
            "reasoning": "Decisión por defecto debido a error en procesamiento",
            "alternative_specialists": [],
            "urgency_level": "media",
            "evaluation_scores": {},
            "error": True,
        }
