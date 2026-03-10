"""Validadores para el sistema médico."""

import logging
import re
from collections import Counter
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

USER_INPUT_BEGIN_MARKER = "<|user_input_begin|>"
USER_INPUT_END_MARKER = "<|user_input_end|>"
PATIENT_RECORD_BEGIN_MARKER = "<|patient_record_begin|>"
PATIENT_RECORD_END_MARKER = "<|patient_record_end|>"

PROMPT_INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "role_tags": re.compile(r"(?i)\[(?:/?system|/?inst)\]|<<\/?sys>>"),
    "directive_headers": re.compile(r"(?im)^(?:system|assistant|developer|human)\s*:\s*"),
    "override_language": re.compile(
        r"(?i)\b(?:ignore (?:all )?previous instructions?|ignore instructions?|"
        r"forget (?:all )?(?:previous|above)|new instructions?|you are now|"
        r"act as|pretend you are|override your|developer mode|jailbreak|"
        r"unrestricted mode|dan)\b"
    ),
}
PROMPT_INJECTION_WARNING_THRESHOLD = 3
_SUSPICIOUS_INPUT_COUNTER: Counter[str] = Counter()


def validate_uuid(value: Any) -> bool:
    """
    Valida si un valor es un UUID válido.

    Args:
        value: Valor a validar

    Returns:
        True si es UUID válido, False otherwise
    """
    try:
        if isinstance(value, UUID):
            return True
        UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def validate_relevance_score(score: float) -> bool:
    """
    Valida un score de relevancia (0-100).

    Args:
        score: Score a validar

    Returns:
        True si está en rango válido
    """
    try:
        return 0 <= float(score) <= 100
    except (ValueError, TypeError):
        return False


def validate_confidence(confidence: float) -> bool:
    """
    Valida un valor de confianza (0.0-1.0).

    Args:
        confidence: Valor de confianza

    Returns:
        True si está en rango válido
    """
    try:
        return 0.0 <= float(confidence) <= 1.0
    except (ValueError, TypeError):
        return False


def validate_message_role(role: str) -> bool:
    """
    Valida que el rol de mensaje sea válido.

    Args:
        role: Rol a validar

    Returns:
        True si es válido
    """
    valid_roles = {"user", "assistant", "system"}
    return role in valid_roles


def sanitize_patient_input(text: str, max_length: int = 5000) -> str:
    """
    Sanitiza input del paciente.

    Args:
        text: Texto a sanitizar
        max_length: Longitud máxima permitida

    Returns:
        Texto sanitizado
    """
    if not isinstance(text, str):
        text = str(text)

    # Truncar si es muy largo
    text = text[:max_length]

    # Remover caracteres de control excepto \n y \t
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Remover múltiples espacios en blanco
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def sanitize_llm_input(text: str, session_id: str | None = None, max_length: int = 5000) -> str:
    """Neutraliza patrones típicos de prompt injection antes de usar el texto en el LLM."""
    sanitized_text = sanitize_patient_input(text, max_length=max_length)
    detected_categories: list[str] = []

    for category, pattern in PROMPT_INJECTION_PATTERNS.items():
        sanitized_text, replacements = pattern.subn("[directive neutralized]", sanitized_text)
        if replacements:
            detected_categories.extend([category] * replacements)

    if detected_categories:
        session_key = session_id or "unknown-session"
        _SUSPICIOUS_INPUT_COUNTER[session_key] += len(detected_categories)
        logger.warning(
            "Prompt injection neutralized for session=%s categories=%s count=%s",
            session_key,
            sorted(set(detected_categories)),
            _SUSPICIOUS_INPUT_COUNTER[session_key],
        )
        if _SUSPICIOUS_INPUT_COUNTER[session_key] >= PROMPT_INJECTION_WARNING_THRESHOLD:
            logger.error(
                "Repeated suspicious prompt injection attempts detected for session=%s",
                session_key,
            )

    return sanitized_text


def format_user_input_for_llm(text: str) -> str:
    """Envuelve el texto del paciente como dato no confiable para el LLM."""
    return f"{USER_INPUT_BEGIN_MARKER}\n{text}\n{USER_INPUT_END_MARKER}"


def format_patient_record_for_llm(text: str) -> str:
    """Envuelve el historial clinico como dato no confiable para el LLM."""
    return f"{PATIENT_RECORD_BEGIN_MARKER}\n{text}\n{PATIENT_RECORD_END_MARKER}"


def validate_specialty_name(specialty: str) -> bool:
    """
    Valida nombre de especialidad.

    Args:
        specialty: Nombre de especialidad

    Returns:
        True si es válido
    """
    if not specialty or not isinstance(specialty, str):
        return False

    # Solo letras, números, guiones bajos y espacios
    pattern = r"^[a-zA-Z0-9_\s]+$"
    return bool(re.match(pattern, specialty))


def validate_json_structure(data: dict, required_keys: list[str]) -> bool:
    """
    Valida que un diccionario tenga las claves requeridas.

    Args:
        data: Diccionario a validar
        required_keys: Lista de claves requeridas

    Returns:
        True si todas las claves están presentes
    """
    if not isinstance(data, dict):
        return False

    return all(key in data for key in required_keys)
