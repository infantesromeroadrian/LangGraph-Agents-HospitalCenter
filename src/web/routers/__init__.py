"""
Routers FastAPI para endpoints REST.
"""

from src.web.routers import health, messages, sessions

__all__ = ["health", "messages", "sessions"]
