"""Entrypoint principal de LangGraph Medical Center."""

import uvicorn

from src.config.settings import settings


def main() -> None:
    """Inicia el servidor FastAPI."""
    settings.print_startup_info()

    uvicorn.run(
        "src.web.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
