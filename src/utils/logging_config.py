"""Configuración de logging para el sistema."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config.settings import settings


class EmojiFormatter(logging.Formatter):
    """Formatter personalizado con emojis por nivel."""

    EMOJI_MAP = {"DEBUG": "🐞", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "💥"}

    def format(self, record):
        """Formatea el log con emoji."""
        emoji = self.EMOJI_MAP.get(record.levelname, "")
        record.emoji = emoji
        return super().format(record)


def setup_logging():
    """Configura el sistema de logging."""

    # Crear directorio de logs si no existe
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Obtener logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Limpiar handlers existentes
    root_logger.handlers.clear()

    # Formato de log
    log_format = "%(asctime)s [%(levelname)8s] %(name)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Handler de consola con emojis
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_formatter = EmojiFormatter(
        fmt="%(asctime)s %(emoji)s [%(levelname)s] %(name)s - %(message)s", datefmt=date_format
    )
    console_handler.setFormatter(console_formatter)

    # Handler de archivo con rotación
    file_handler = RotatingFileHandler(
        filename=settings.LOG_FILE,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # Log todo al archivo
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

    # Añadir handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silenciar loggers ruidosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info("ℹ️ Sistema de logging configurado")
    logging.info(f"ℹ️ Nivel de log: {settings.LOG_LEVEL}")
    logging.info(f"ℹ️ Archivo de log: {settings.LOG_FILE}")


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado.

    Args:
        name: Nombre del logger (usualmente __name__)

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
