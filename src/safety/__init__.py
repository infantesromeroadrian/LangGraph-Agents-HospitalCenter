"""Salvaguardas clínicas deterministas (sin LLM)."""

from src.safety.output_guard import GuardResult, apply_output_guard, find_violations
from src.safety.red_flags import (
    EMERGENCY_NUMBER,
    RedFlag,
    build_emergency_message,
    detect_red_flags,
)

__all__ = [
    "EMERGENCY_NUMBER",
    "GuardResult",
    "RedFlag",
    "apply_output_guard",
    "build_emergency_message",
    "detect_red_flags",
    "find_violations",
]
