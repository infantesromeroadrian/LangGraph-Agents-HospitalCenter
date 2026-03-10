"""
Modelos Pydantic para gestión de pacientes.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.utils.validators import sanitize_patient_input


class PatientCreate(BaseModel):
    """Modelo para crear un nuevo paciente."""

    # Datos personales
    full_name: str = Field(
        ..., min_length=3, max_length=255, description="Nombre completo del paciente"
    )
    age: int = Field(..., ge=0, le=120, description="Edad del paciente")
    gender: str = Field(..., pattern="^(M|F|O|N)$", description="Género: M/F/O/N")
    dni: Optional[str] = Field(None, max_length=50, description="DNI/Documento de identidad")
    email: Optional[EmailStr] = Field(None, description="Email del paciente")
    phone: Optional[str] = Field(None, max_length=50, description="Teléfono de contacto")

    # Información médica
    allergies: str = Field(default="Ninguna conocida", description="Alergias conocidas")
    medications: str = Field(default="Ninguna", description="Medicación actual")
    medical_history: str = Field(
        default="Sin antecedentes relevantes", description="Antecedentes médicos y cirugías previas"
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Valida que el nombre no esté vacío."""
        cleaned_name = sanitize_patient_input(v, max_length=255)
        if not cleaned_name:
            raise ValueError("El nombre no puede estar vacío")
        return cleaned_name

    @field_validator("allergies", "medications", "medical_history")
    @classmethod
    def validate_medical_fields(cls, v: str) -> str:
        """Limpia campos médicos."""
        return sanitize_patient_input(v, max_length=5000) if v else "No especificado"


class PatientUpdate(BaseModel):
    """Modelo para actualizar datos de un paciente."""

    full_name: Optional[str] = Field(None, min_length=3, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[str] = Field(None, pattern="^(M|F|O|N)$")
    dni: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    allergies: Optional[str] = None
    medications: Optional[str] = None
    medical_history: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_optional_full_name(cls, v: Optional[str]) -> Optional[str]:
        """Limpia el nombre si se proporciona en una actualizacion."""
        if v is None:
            return v
        cleaned_name = sanitize_patient_input(v, max_length=255)
        if not cleaned_name:
            raise ValueError("El nombre no puede estar vacío")
        return cleaned_name

    @field_validator("allergies", "medications", "medical_history")
    @classmethod
    def validate_optional_medical_fields(cls, v: Optional[str]) -> Optional[str]:
        """Limpia campos medicos opcionales."""
        if v is None:
            return v
        return sanitize_patient_input(v, max_length=5000)


class PatientResponse(BaseModel):
    """Modelo de respuesta para un paciente."""

    id: UUID
    full_name: str
    age: int
    gender: str
    dni: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    allergies: str
    medications: str
    medical_history: str
    medical_record_number: str
    created_at: datetime
    updated_at: datetime
    last_visit: datetime

    class Config:
        """Configuración del modelo."""

        from_attributes = True


class PatientSummary(BaseModel):
    """Resumen de paciente para mostrar en listas."""

    id: UUID
    full_name: str
    medical_record_number: str
    age: int
    last_visit: datetime

    class Config:
        """Configuración del modelo."""

        from_attributes = True


class PatientContextForLLM(BaseModel):
    """
    Contexto del paciente para enviar al LLM.

    Este modelo contiene la información médica relevante que los agentes
    necesitan conocer para dar un diagnóstico personalizado.
    """

    full_name: str
    age: int
    gender: str
    allergies: str
    medications: str
    medical_history: str
    medical_record_number: str

    def to_context_string(self) -> str:
        """
        Convierte los datos del paciente en un string formateado para el LLM.

        Returns:
            String con el contexto del paciente formateado
        """
        gender_map = {"M": "Masculino", "F": "Femenino", "O": "Otro", "N": "No especificado"}

        return f"""INFORMACIÓN DEL PACIENTE (Historia Clínica: {self.medical_record_number}):

Datos Personales:
- Nombre: {self.full_name}
- Edad: {self.age} años
- Género: {gender_map.get(self.gender, self.gender)}

Información Médica Relevante:
- Alergias: {self.allergies}
- Medicación Actual: {self.medications}
- Antecedentes Médicos: {self.medical_history}

IMPORTANTE: Considera esta información al evaluar los síntomas y dar recomendaciones.
Si hay alergias, NO recomendar medicamentos que las contengan.
Si hay medicación actual, verificar posibles interacciones.
"""
