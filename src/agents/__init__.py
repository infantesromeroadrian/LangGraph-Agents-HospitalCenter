"""Módulo de agentes médicos especializados."""

from src.agents.base_agent import BaseMedicalAgent
from src.agents.consensus_agent import ConsensusAgent
from src.agents.triage_agent import TriageAgent

__all__ = ["BaseMedicalAgent", "ConsensusAgent", "TriageAgent"]
