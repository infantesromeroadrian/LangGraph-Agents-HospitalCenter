"""Especialistas médicos del sistema."""

from src.agents.specialists.cardiology import CardiologyAgent
from src.agents.specialists.dermatology import DermatologyAgent
from src.agents.specialists.general_medicine import GeneralMedicineAgent
from src.agents.specialists.neurology import NeurologyAgent
from src.agents.specialists.oncology import OncologyAgent
from src.agents.specialists.orthopedics import OrthopedicsAgent
from src.agents.specialists.pediatrics import PediatricsAgent
from src.agents.specialists.psychiatry import PsychiatryAgent

__all__ = [
    "CardiologyAgent",
    "DermatologyAgent",
    "GeneralMedicineAgent",
    "NeurologyAgent",
    "OncologyAgent",
    "OrthopedicsAgent",
    "PediatricsAgent",
    "PsychiatryAgent",
]
