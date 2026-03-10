"""Configuración del sistema médico."""

from typing import Literal

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración global del sistema."""

    # OpenAI Configuration
    OPENAI_API_KEY: str = Field(default="your_openai_api_key_here", description="API Key de OpenAI")
    GROQ_API_KEY: str = Field(default="", description="API Key de Groq (opcional)")
    OPENAI_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL compatible con OpenAI (OpenAI, Groq, etc.)",
    )
    OPENAI_MODEL: str = Field(default="gpt-4o", description="Modelo de OpenAI a usar")
    OPENAI_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    OPENAI_MAX_TOKENS: int = Field(default=2000, gt=0)
    OPENAI_TIMEOUT: int = Field(default=60, description="Timeout en segundos")

    # PostgreSQL Configuration
    DATABASE_URL: str = Field(
        default="postgresql://medical_user:medical_password@localhost:5432/medical_db",
        description="URL de conexión PostgreSQL",
    )
    DB_POOL_SIZE: int = Field(default=10, gt=0)
    DB_MAX_OVERFLOW: int = Field(default=20, gt=0)
    DB_ECHO: bool = Field(default=False, description="Log SQL queries")

    # Application Configuration (FastAPI)
    APP_HOST: str = Field(default="0.0.0.0", description="Host para el servidor")
    APP_PORT: int = Field(default=5000, gt=0, lt=65536, description="Puerto del servidor")
    APP_DEBUG: bool = Field(default=False, description="Modo debug (solo desarrollo)")
    APP_SECRET_KEY: str = Field(default="dev-secret-key-change-in-production")

    # LangGraph Configuration
    RECURSION_LIMIT: int = Field(default=50, gt=0, description="Límite de recursión del grafo")
    CHECKPOINT_DB_URL: str = Field(default="", description="URL para checkpointing")

    # Logging Configuration
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    LOG_FILE: str = Field(default="logs/medical_system.log")
    LOG_MAX_BYTES: int = Field(default=10485760, description="10MB")
    LOG_BACKUP_COUNT: int = Field(default=5)

    # Security
    CORS_ORIGINS: str = Field(default="http://localhost:5000,http://127.0.0.1:5000")
    RATE_LIMIT: str = Field(default="100/hour")

    # Medical System Configuration
    MAX_PARALLEL_EVALUATIONS: int = Field(default=8, description="Número de especialistas")
    TRIAGE_CONFIDENCE_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    CONSENSUS_VOTING_WEIGHT: Literal["balanced", "weighted", "unanimous"] = Field(
        default="balanced"
    )

    @validator("CHECKPOINT_DB_URL", pre=True, always=True)
    def set_checkpoint_url(cls, v, values):
        """Usar DATABASE_URL si no se especifica CHECKPOINT_DB_URL."""
        if not v and "DATABASE_URL" in values:
            return values["DATABASE_URL"]
        return v

    @validator("CORS_ORIGINS")
    def parse_cors_origins(cls, v):
        """Parsear CORS_ORIGINS como lista."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        """Configuración de Pydantic."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def get_cors_origins_list(self) -> list[str]:
        """Obtiene la lista de orígenes CORS."""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    def validate_config(self) -> bool:
        """Valida la configuración crítica."""
        critical_checks = [
            (self.OPENAI_API_KEY != "your_openai_api_key_here", "OPENAI_API_KEY no configurada"),
            (self.OPENAI_BASE_URL.startswith("http"), "OPENAI_BASE_URL inválida"),
            (self.DATABASE_URL and "postgresql://" in self.DATABASE_URL, "DATABASE_URL inválida"),
            (
                self.APP_SECRET_KEY != "dev-secret-key-change-in-production"
                if not self.APP_DEBUG
                else True,
                "APP_SECRET_KEY debe cambiarse en producción",
            ),
        ]

        for check, error_msg in critical_checks:
            if not check:
                raise ValueError(f"Configuración inválida: {error_msg}")

        return True

    def print_startup_info(self):
        """Imprime información de inicio (sin secrets)."""
        print("ℹ️ Configuración del Sistema Médico")
        print(f"   - Modelo LLM: {self.OPENAI_MODEL}")
        print(f"   - Endpoint LLM: {self.OPENAI_BASE_URL}")
        print(f"   - Server: FastAPI on {self.APP_HOST}:{self.APP_PORT}")
        print(f"   - Debug: {self.APP_DEBUG}")
        print(f"   - Log Level: {self.LOG_LEVEL}")
        print(f"   - Especialistas: {self.MAX_PARALLEL_EVALUATIONS}")
        print(f"   - Recursion Limit: {self.RECURSION_LIMIT}")


# Instancia global de configuración
settings = Settings()
