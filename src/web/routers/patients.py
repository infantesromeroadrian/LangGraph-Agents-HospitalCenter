"""
Router de FastAPI para gestión de pacientes.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from src.models.patient import (
    PatientContextForLLM,
    PatientCreate,
    PatientResponse,
    PatientSummary,
    PatientUpdate,
)
from src.services.database_service import db_service

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_medical_record_number() -> str:
    """
    Genera un número de historia clínica único.

    Formato: HC-YYYY-XXXXXX
    Ejemplo: HC-2025-001234

    Returns:
        String con el número de historia clínica
    """
    import random

    year = datetime.now().year
    random_num = random.randint(100000, 999999)
    return f"HC-{year}-{random_num}"


@router.post("/patients", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(patient_data: PatientCreate) -> PatientResponse:
    """
    Crea un nuevo paciente en la base de datos.

    Args:
        patient_data: Datos del paciente a crear

    Returns:
        Datos del paciente creado con su ID y número de historia clínica

    Raises:
        HTTPException: Si hay error al crear el paciente
    """
    try:
        # Generar número de historia clínica único
        medical_record_number = generate_medical_record_number()

        # Verificar que no exista (muy improbable, pero por seguridad)
        existing = await db_service.execute_query(
            """
            SELECT id FROM patients WHERE medical_record_number = $1
            """,
            medical_record_number,
        )

        if existing:
            # Si existe, regenerar
            medical_record_number = generate_medical_record_number()

        # Insertar paciente en la base de datos
        query = """
            INSERT INTO patients (
                full_name, age, gender, dni, email, phone,
                allergies, medications, medical_history,
                medical_record_number
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """

        result = await db_service.execute_query(
            query,
            patient_data.full_name,
            patient_data.age,
            patient_data.gender,
            patient_data.dni,
            patient_data.email,
            patient_data.phone,
            patient_data.allergies,
            patient_data.medications,
            patient_data.medical_history,
            medical_record_number,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear el paciente",
            )

        patient_record = result[0]

        logger.info(f"✅ Paciente creado: {medical_record_number} - {patient_data.full_name}")

        return PatientResponse(
            id=patient_record["id"],
            full_name=patient_record["full_name"],
            age=patient_record["age"],
            gender=patient_record["gender"],
            dni=patient_record["dni"],
            email=patient_record["email"],
            phone=patient_record["phone"],
            allergies=patient_record["allergies"],
            medications=patient_record["medications"],
            medical_history=patient_record["medical_history"],
            medical_record_number=patient_record["medical_record_number"],
            created_at=patient_record["created_at"],
            updated_at=patient_record["updated_at"],
            last_visit=patient_record["last_visit"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creando paciente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear paciente: {e!s}",
        ) from e


@router.get("/patients/{medical_record_number}", response_model=PatientResponse)
async def get_patient(medical_record_number: str) -> PatientResponse:
    """
    Obtiene los datos de un paciente por su número de historia clínica.

    Args:
        medical_record_number: Número de historia clínica (HC-YYYY-XXXXXX)

    Returns:
        Datos completos del paciente

    Raises:
        HTTPException: Si el paciente no existe
    """
    try:
        query = """
            SELECT * FROM patients
            WHERE medical_record_number = $1
        """

        result = await db_service.execute_query(query, medical_record_number)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado"
            )

        patient_record = result[0]

        # Actualizar last_visit
        await db_service.execute_query(
            """
            UPDATE patients SET last_visit = CURRENT_TIMESTAMP
            WHERE medical_record_number = $1
            """,
            medical_record_number,
        )

        logger.info(f"📋 Paciente consultado: {medical_record_number}")

        return PatientResponse(
            id=patient_record["id"],
            full_name=patient_record["full_name"],
            age=patient_record["age"],
            gender=patient_record["gender"],
            dni=patient_record["dni"],
            email=patient_record["email"],
            phone=patient_record["phone"],
            allergies=patient_record["allergies"],
            medications=patient_record["medications"],
            medical_history=patient_record["medical_history"],
            medical_record_number=patient_record["medical_record_number"],
            created_at=patient_record["created_at"],
            updated_at=patient_record["updated_at"],
            last_visit=patient_record["last_visit"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo paciente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener paciente: {e!s}",
        ) from e


@router.get("/patients/{medical_record_number}/context", response_model=PatientContextForLLM)
async def get_patient_context_for_llm(medical_record_number: str) -> PatientContextForLLM:
    """
    Obtiene el contexto del paciente formateado para el LLM.

    Este endpoint devuelve solo la información médica relevante que
    los agentes necesitan para dar diagnósticos personalizados.

    Args:
        medical_record_number: Número de historia clínica

    Returns:
        Contexto del paciente para el LLM
    """
    patient = await get_patient(medical_record_number)

    return PatientContextForLLM(
        full_name=patient.full_name,
        age=patient.age,
        gender=patient.gender,
        allergies=patient.allergies,
        medications=patient.medications,
        medical_history=patient.medical_history,
        medical_record_number=patient.medical_record_number,
    )


@router.patch("/patients/{medical_record_number}", response_model=PatientResponse)
async def update_patient(
    medical_record_number: str, patient_data: PatientUpdate
) -> PatientResponse:
    """
    Actualiza los datos de un paciente existente.

    Args:
        medical_record_number: Número de historia clínica
        patient_data: Datos a actualizar (solo los campos proporcionados)

    Returns:
        Datos actualizados del paciente
    """
    try:
        # Verificar que el paciente existe
        existing = await db_service.execute_query(
            "SELECT id FROM patients WHERE medical_record_number = $1", medical_record_number
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado"
            )

        # Construir query de actualización solo con campos proporcionados
        update_fields = []
        update_values = []
        param_num = 1

        for field, value in patient_data.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ${param_num}")
                update_values.append(value)
                param_num += 1

        if not update_fields:
            # No hay nada que actualizar, retornar paciente actual
            return await get_patient(medical_record_number)

        # Añadir medical_record_number como último parámetro
        update_values.append(medical_record_number)

        query = f"""
            UPDATE patients
            SET {", ".join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE medical_record_number = ${param_num}
            RETURNING *
        """

        result = await db_service.execute_query(query, *update_values)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al actualizar paciente",
            )

        patient_record = result[0]

        logger.info(f"📝 Paciente actualizado: {medical_record_number}")

        return PatientResponse(
            id=patient_record["id"],
            full_name=patient_record["full_name"],
            age=patient_record["age"],
            gender=patient_record["gender"],
            dni=patient_record["dni"],
            email=patient_record["email"],
            phone=patient_record["phone"],
            allergies=patient_record["allergies"],
            medications=patient_record["medications"],
            medical_history=patient_record["medical_history"],
            medical_record_number=patient_record["medical_record_number"],
            created_at=patient_record["created_at"],
            updated_at=patient_record["updated_at"],
            last_visit=patient_record["last_visit"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error actualizando paciente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar paciente: {e!s}",
        ) from e


@router.get("/patients", response_model=list[PatientSummary])
async def list_patients(limit: int = 50, offset: int = 0) -> list[PatientSummary]:
    """
    Lista todos los pacientes (resumen).

    Args:
        limit: Número máximo de pacientes a retornar
        offset: Número de pacientes a saltar (paginación)

    Returns:
        Lista de pacientes (solo datos básicos)
    """
    try:
        query = """
            SELECT id, full_name, medical_record_number, age, last_visit
            FROM patients
            ORDER BY last_visit DESC
            LIMIT $1 OFFSET $2
        """

        results = await db_service.execute_query(query, limit, offset)

        return [
            PatientSummary(
                id=row["id"],
                full_name=row["full_name"],
                medical_record_number=row["medical_record_number"],
                age=row["age"],
                last_visit=row["last_visit"],
            )
            for row in results
        ]

    except Exception as e:
        logger.error(f"❌ Error listando pacientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar pacientes: {e!s}",
        ) from e
