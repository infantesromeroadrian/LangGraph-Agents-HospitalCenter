"""Validadores para el sistema médico."""

import re
from typing import Any
from uuid import UUID


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
