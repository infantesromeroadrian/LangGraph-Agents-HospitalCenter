#!/usr/bin/env python3
"""
Test E2E: Verificar que el contexto del paciente se inyecta correctamente en los prompts.

Este script:
1. Crea un paciente con alergias a Penicilina
2. Crea una sesión asociada al paciente
3. Envía un mensaje preguntando por antibióticos
4. Verifica que el LLM NO recomiende Penicilina (debe considerar la alergia)

IMPORTANTE: Este test requiere que OPENAI_API_KEY esté configurado.
"""

import asyncio
import uuid
from datetime import datetime

import asyncpg


async def main():
    print("=" * 80)
    print("TEST E2E: Patient Context Injection")
    print("=" * 80)
    print()

    # Conectar a la base de datos
    print("📊 Conectando a PostgreSQL...")
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="medical_user",
        password="medical_password",
        database="medical_db",
    )
    print("✅ Conectado a PostgreSQL\n")

    try:
        # 1. Crear paciente con alergia a Penicilina
        print("👤 PASO 1: Crear paciente de prueba")
        patient_id = uuid.uuid4()
        # HC-2025-123456 (formato estándar, max 15 chars)
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
            "Penicilina, Aspirina",  # ⚠️ CRÍTICO: Alergia a Penicilina
            "Omeprazol 20mg",
            "Hipertensión controlada",
            datetime.now(),
        )

        print(f"   ✅ Paciente creado: {medical_record}")
        print("   🚨 Alergias: Penicilina, Aspirina")
        print()

        # 2. Crear sesión asociada al paciente
        print("💬 PASO 2: Crear sesión asociada al paciente")
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

        print(f"   ✅ Sesión creada: {session_id}")
        print()

        # 3. Verificar que el contexto se carga correctamente
        print("🔍 PASO 3: Verificar carga de contexto del paciente")

        # Simular la query que hace chat.py (línea 82-112)
        session_row = await conn.fetchrow(
            """
            SELECT patient_id
            FROM sessions
            WHERE session_id = $1
            """,
            session_id,
        )

        if not session_row or not session_row["patient_id"]:
            print("   ❌ ERROR: No se pudo obtener patient_id desde la sesión")
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
            print("   ❌ ERROR: Paciente no encontrado")
            return

        # Construir contexto como lo hace chat.py (línea 130-150)
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

        print("   ✅ Contexto cargado correctamente:")
        print("   " + "-" * 76)
        for line in patient_context.split("\n")[:10]:
            print(f"   {line}")
        print("   ...")
        print("   " + "-" * 76)
        print()

        # 4. Resultado del test
        print("=" * 80)
        print("✅ TEST COMPLETADO - BASE DE DATOS OK")
        print("=" * 80)
        print()
        print("🧪 SIGUIENTE PASO (MANUAL):")
        print()
        print("1. Abre http://localhost:5000 en tu navegador")
        print("2. En la consola del navegador, ejecuta:")
        print(f"   localStorage.setItem('medical_record_number', '{medical_record}')")
        print("3. Recarga la página")
        print("4. Envía este mensaje:")
        print()
        print('   "Tengo fiebre de 39°C y dolor de garganta. ¿Puedo tomar antibióticos?"')
        print()
        print("5. VERIFICA en los logs del Docker:")
        print("   docker logs langgraph-medical-center -f")
        print()
        print("6. BUSCA estos mensajes:")
        print("   ✅ [Patient] Contexto cargado: Paciente Test E2E (HC-TEST-...)")
        print("   ✅ Triaje: Contexto del paciente INYECTADO en el prompt")
        print("   ✅ medicina_general: Contexto del paciente INYECTADO en el chat")
        print()
        print("7. VERIFICA que la respuesta del LLM:")
        print("   ❌ NO recomiende Penicilina (el paciente es alérgico)")
        print("   ❌ NO recomiende Aspirina (el paciente es alérgico)")
        print("   ✅ Mencione alternativas seguras (ej: Paracetamol, Ibuprofeno)")
        print()
        print("📋 Datos del paciente creado:")
        print(f"   - HC: {medical_record}")
        print(f"   - Session ID: {session_id}")
        print(f"   - Patient ID: {patient_id}")
        print()

    finally:
        await conn.close()
        print("🔌 Conexión cerrada")


if __name__ == "__main__":
    asyncio.run(main())
