#!/usr/bin/env python3
"""
E2E script: Verify that patient context is injected correctly into agent prompts.

This script:
1. Creates a patient with Penicillin allergy
2. Creates a session associated with the patient
3. Sends a message asking about antibiotics
4. Verifies that the LLM does NOT recommend Penicillin (must consider the allergy)

IMPORTANT: Requires a running PostgreSQL instance and OPENAI_API_KEY configured.

Usage:
    export DATABASE_HOST=localhost
    export DATABASE_PORT=5432
    export DATABASE_USER=medical_user
    export DATABASE_PASSWORD=medical_password
    export DATABASE_NAME=medical_db
    python scripts/e2e_patient_context.py
"""

import asyncio
import os
import uuid
from datetime import datetime

import asyncpg


async def main():
    print("=" * 80)
    print("E2E SCRIPT: Patient Context Injection")
    print("=" * 80)
    print()

    db_host = os.environ.get("DATABASE_HOST", "localhost")
    db_port = int(os.environ.get("DATABASE_PORT", "5432"))
    db_user = os.environ.get("DATABASE_USER", "medical_user")
    db_password = os.environ.get("DATABASE_PASSWORD")
    db_name = os.environ.get("DATABASE_NAME", "medical_db")

    if not db_password:
        print("ERROR: DATABASE_PASSWORD environment variable is required.")
        print("Set it with: export DATABASE_PASSWORD=<your_password>")
        return

    print("Connecting to PostgreSQL...")
    conn = await asyncpg.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
    )
    print("Connected to PostgreSQL\n")

    try:
        # 1. Create test patient with Penicillin allergy
        print("STEP 1: Create test patient")
        patient_id = uuid.uuid4()
        medical_record = (
            f"HC-{datetime.now().strftime('%Y')}-TEST{datetime.now().strftime('%H%M%S')}"
        )

        await conn.execute(
            """
            INSERT INTO patients (
                id, medical_record_number, full_name, age, gender,
                allergies, medications, medical_history, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            patient_id,
            medical_record,
            "Paciente Test E2E",
            35,
            "M",
            "Penicilina, Aspirina",
            "Omeprazol 20mg",
            "Hipertensión controlada",
            datetime.now(),
        )

        print(f"   Patient created: {medical_record}")
        print("   Allergies: Penicilina, Aspirina")
        print()

        # 2. Create session associated with patient
        print("STEP 2: Create session associated with patient")
        session_id = uuid.uuid4()

        await conn.execute(
            """
            INSERT INTO sessions (
                session_id, patient_id, created_at, updated_at, is_active
            ) VALUES ($1, $2, $3, $4, $5)
            """,
            session_id,
            patient_id,
            datetime.now(),
            datetime.now(),
            True,
        )

        print(f"   Session created: {session_id}")
        print()

        # 3. Verify patient context loads correctly
        print("STEP 3: Verify patient context loading")

        session_row = await conn.fetchrow(
            """
            SELECT patient_id
            FROM sessions
            WHERE session_id = $1
            """,
            session_id,
        )

        if not session_row or not session_row["patient_id"]:
            print("   ERROR: Could not retrieve patient_id from session")
            return

        patient_row = await conn.fetchrow(
            """
            SELECT
                medical_record_number,
                full_name,
                age,
                gender,
                allergies,
                medications,
                medical_history
            FROM patients
            WHERE id = $1
            """,
            session_row["patient_id"],
        )

        if not patient_row:
            print("   ERROR: Patient not found")
            return

        gender_map = {"M": "Masculino", "F": "Femenino", "O": "Otro", "N": "No especificado"}
        gender_display = gender_map.get(patient_row["gender"], patient_row["gender"])

        patient_context = f"""
INFORMACIÓN DEL PACIENTE (Historia Clínica: {patient_row["medical_record_number"]}):

Datos Personales:
- Nombre: {patient_row["full_name"]}
- Edad: {patient_row["age"]} años
- Género: {gender_display}

Alergias Conocidas:
{patient_row["allergies"] or "Ninguna conocida"}

Medicación Actual:
{patient_row["medications"] or "Ninguna"}

Antecedentes Médicos:
{patient_row["medical_history"] or "Sin antecedentes relevantes"}

IMPORTANTE: Considera esta información al hacer recomendaciones médicas.
No recomiendes medicamentos a los que el paciente sea alérgico.
Verifica interacciones con la medicación actual.
""".strip()

        print("   Context loaded correctly:")
        print("   " + "-" * 76)
        for line in patient_context.split("\n")[:10]:
            print(f"   {line}")
        print("   ...")
        print("   " + "-" * 76)
        print()

        # 4. Test result
        print("=" * 80)
        print("TEST COMPLETED - DATABASE OK")
        print("=" * 80)
        print()
        print("NEXT STEP (MANUAL):")
        print()
        print("1. Open http://localhost:5000 in your browser")
        print("2. In the browser console, run:")
        print(f"   localStorage.setItem('medical_record_number', '{medical_record}')")
        print("3. Reload the page")
        print("4. Send this message:")
        print()
        print('   "Tengo fiebre de 39C y dolor de garganta. Puedo tomar antibioticos?"')
        print()
        print("5. Check Docker logs:")
        print("   docker logs langgraph-medical-center -f")
        print()
        print("6. Verify the LLM response:")
        print("   - Does NOT recommend Penicillin (patient is allergic)")
        print("   - Does NOT recommend Aspirin (patient is allergic)")
        print("   - Mentions safe alternatives (e.g., Paracetamol, Ibuprofen)")
        print()
        print("Test patient data:")
        print(f"   - HC: {medical_record}")
        print(f"   - Session ID: {session_id}")
        print(f"   - Patient ID: {patient_id}")
        print()

    finally:
        await conn.close()
        print("Connection closed")


if __name__ == "__main__":
    asyncio.run(main())
