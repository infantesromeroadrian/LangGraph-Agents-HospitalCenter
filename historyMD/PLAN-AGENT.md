# 🏥 PLAN DE AUDITORÍA Y MEJORAS - LangGraph Medical Center

**Fecha:** 28 de diciembre de 2025
**Versión Actual:** 1.0.0
**Estado del Proyecto:** Production Ready (con issues conocidos)
**Líneas de Código:** ~3,597 Python + 600 web

---

## 📊 RESUMEN EJECUTIVO

### Calificación General del Proyecto: **6.2/10**

| Aspecto | Score | Estado |
|---------|-------|--------|
| **Modularidad** | 8/10 | ✅ Buena |
| **Mantenibilidad** | 7/10 | 🟡 Mejorable |
| **Escalabilidad** | 5/10 | 🔴 Requiere trabajo |
| **Testabilidad** | 6/10 | 🟡 Mejorable |
| **Seguridad** | 4/10 | 🔴 Crítico |
| **Performance** | 6/10 | 🟡 Mejorable |
| **Resiliencia** | 5/10 | 🔴 Requiere trabajo |

### Hallazgos Clave

**✅ Fortalezas:**
- Arquitectura de agentes bien diseñada (Template Method + Factory)
- Uso apropiado de LangGraph (fan-out/fan-in paralelo)
- Separación clara de responsabilidades
- Documentación completa y profesional
- Docker optimizado con UV (builds en 30s)

**❌ Debilidades Críticas:**
- Incompatibilidad Flask + eventlet + asyncpg (persistencia deshabilitada)
- Sin autenticación ni autorización
- Datos médicos sin encriptación
- Checkpointer en memoria (no persistente)
- Singletons globales dificultan testing
- Cobertura de tests <20%

### Prioridad de Acciones

```
INMEDIATO (Esta semana):
├── Fix bug en get_messages (línea 196-198 app.py)
├── Crear .env.example template
└── Documentar issues conocidos ✅ (ya hecho)

CORTO PLAZO (2 semanas):
├── Migrar a FastAPI (CRÍTICO)
├── Implementar AsyncPostgresSaver
├── Tests de integración básicos
└── Encriptación de patient_info

MEDIANO PLAZO (1 mes):
├── Sistema de autenticación (JWT)
├── Cache con Redis
├── Circuit breaker en LLMService
├── Observabilidad (métricas + tracing)
└── Cobertura de tests >80%

LARGO PLAZO (2-3 meses):
├── Kubernetes deployment
├── CI/CD completo
├── Security scanning
└── Performance optimization
```

---

## 🔍 ANÁLISIS DETALLADO DE LA ARQUITECTURA ACTUAL

### 1. Stack Tecnológico

**Backend:**
```
Flask 3.1.0
├── Flask-SocketIO 5.4.1 (WebSocket)
├── eventlet 0.37.0 (async mode) ⚠️ PROBLEMA
├── Gunicorn 23.0.0 (production server)
└── asyncpg 0.30.0 (PostgreSQL async) ⚠️ CONFLICTO
```

**LangGraph & AI:**
```
LangGraph 0.2.45
├── LangChain 0.3.10
├── LangChain-OpenAI 0.2.9
└── OpenAI 1.57.4 (GPT-5.1)
```

**Database:**
```
PostgreSQL 15-alpine
├── asyncpg 0.30.0 (async driver) ⚠️
├── SQLAlchemy 2.0.36 (no usado actualmente)
└── psycopg2-binary 2.9.10 (instalado pero no usado)
```

**Frontend:**
```
Vanilla JavaScript
├── Socket.IO client
├── Bootstrap 5
└── D3.js (referenciado, no implementado)
```

### 2. Arquitectura de Agentes

```
BaseMedicalAgent (Abstract)
├── Template Method pattern
├── Dependency Injection (LLMService)
└── Métodos comunes: evaluate(), chat(), get_specialty_info()

Especialistas (8 agentes):
├── CardiologyAgent        → Problemas cardiovasculares
├── NeurologyAgent         → Sistema nervioso
├── PediatricsAgent        → Salud infantil
├── DermatologyAgent       → Piel y afecciones cutáneas
├── OrthopedicsAgent       → Huesos y articulaciones
├── PsychiatryAgent        → Salud mental
├── OncologyAgent          → Detección de cáncer
└── GeneralMedicineAgent   → Atención primaria

Agentes de Coordinación:
├── TriageAgent           → Clasificación inicial
├── ConsensusAgent        → Selección de especialista
└── AgentFactory          → Creación de agentes
```

### 3. Flujo del Grafo LangGraph

```
                    ┌─────────────┐
                    │   ENTRADA   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   TRIAJE    │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
    ┌─────────▼─────────┐      ┌───────▼────────┐
    │ EVALUACIÓN PARALELA│      │  CHAT DIRECTO  │
    │   (Fan-out 8x)     │      │ (especialista  │
    └─────────┬─────────┘      │   asignado)    │
              │                 └────────┬───────┘
      ┌───────▼────────┐                │
      │ Cardiology     │                │
      │ Neurology      │                │
      │ Pediatrics     │                │
      │ Dermatology    │                │
      │ Orthopedics    │                │
      │ Psychiatry     │                │
      │ Oncology       │                │
      │ General Med    │                │
      └───────┬────────┘                │
              │ (Fan-in)                │
      ┌───────▼────────┐                │
      │   CONSENSO     │                │
      │  (selección)   │                │
      └───────┬────────┘                │
              │                         │
              └────────┬────────────────┘
                       │
              ┌────────▼────────┐
              │ SPECIALIST CHAT │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │      END        │
              └─────────────────┘
```

### 4. Persistencia y Estado

**Estado del Grafo (MedicalGraphState):**
```python
@dataclass
class MedicalGraphState:
    session_id: UUID
    thread_id: str
    messages: list[Message]
    evaluations: list[SpecialistEvaluation]
    selected_specialist: Optional[str]
    active_specialist: Optional[str]
    needs_parallel_evaluation: bool
    triage_completed: bool
    consensus_data: dict
```

**Persistencia Actual:**
```
LangGraph Checkpointer:
├── Tipo: MemorySaver ⚠️ TEMPORAL
├── Problema: No persiste entre reinicios
└── Solución: Migrar a AsyncPostgresSaver

Base de Datos (PostgreSQL):
├── sessions (metadata de sesiones)
├── messages (historial de chat) ⚠️ DESHABILITADO
├── specialist_evaluations (evaluaciones)
└── checkpoints/checkpoint_writes (no usado)
```

### 5. Comunicación Cliente-Servidor

**Protocolo WebSocket:**
```
Cliente                    Servidor
  │
  ├─ connect ──────────────>│ Establece conexión
  │<────────── connected ───┤
  │
  ├─ join_session(id) ─────>│ Une a sala de sesión
  │<────────── joined ──────┤
  │
  ├─ user_message(msg) ────>│ Envía consulta médica
  │                         │
  │                         │ [Ejecuta grafo]
  │<── agent_thinking ──────┤ "Procesando..."
  │<── graph_update ────────┤ Nodo ejecutado: triage
  │<── graph_update ────────┤ Nodo ejecutado: evaluation
  │<── graph_update ────────┤ Nodo ejecutado: consensus
  │<── agent_response ──────┤ Respuesta del especialista
  │
```

**Endpoints REST:**
```
POST   /api/sessions              → Crear sesión
GET    /api/sessions/<id>         → Info de sesión
GET    /api/sessions/<id>/messages → Historial (⚠️ BUG)
GET    /health                     → Health check
GET    /                           → UI web
```

---

## 🐛 ISSUES IDENTIFICADOS (PRIORIZADOS)

### 🔴 CRÍTICOS - Requieren Acción Inmediata

#### **ISSUE #1: Conflicto Event Loop (eventlet + asyncpg)**

**Ubicación:** `src/web/app.py:378-381`

**Problema:**
```python
# Línea 378-381
# NOTE: Guardado de mensajes deshabilitado temporalmente
# debido a event loop conflicts con eventlet + asyncpg
# TODO: Migrar a FastAPI o implementar queue-based persistence
# Alternativa: usar sync DB driver (psycopg2) en lugar de asyncpg
```

**Causa Raíz:**
- Flask + eventlet monkey-patches asyncio
- asyncpg espera un event loop consistente
- `run_until_complete()` en background tasks usa loop diferente
- Resultado: "Task got Future attached to a different loop"

**Impacto:**
- 🔴 **ALTO:** Mensajes no se persisten en DB
- Sesiones se pierden al reiniciar
- Solo funciona en memoria durante ejecución

**Soluciones Propuestas:**

**Opción A: Migrar a FastAPI** ⭐ **RECOMENDADO**
```python
# Pros:
- Native async/await (sin eventlet)
- asyncpg funciona perfectamente
- 30-40% mejor performance
- Auto-documentación OpenAPI
- Validación con Pydantic integrada

# Contras:
- 2-3 días de migración
- Reescribir WebSocket handlers
- Cambio de paradigma (menor)

# Esfuerzo: 2-3 días
# Riesgo: Medio
# Beneficio: ⭐⭐⭐⭐⭐
```

**Opción B: psycopg2 (sync driver)**
```python
# Pros:
- Fix rápido (1-2 horas)
- Compatible con eventlet
- No requiere cambio de framework

# Contras:
- Bloquea workers
- Menor throughput
- Patrón menos moderno

# Esfuerzo: 2 horas
# Riesgo: Bajo
# Beneficio: ⭐⭐
```

**Opción C: Message Queue (Redis/RabbitMQ)**
```python
# Pros:
- Desacopla persistencia
- Mantiene asyncpg
- Escalable

# Contras:
- Infraestructura adicional
- Complejidad
- Eventual consistency

# Esfuerzo: 3-4 días
# Riesgo: Alto
# Beneficio: ⭐⭐⭐
```

**Decisión Recomendada:** **Opción A (FastAPI)**

---

#### **ISSUE #2: Bug en Endpoint get_messages**

**Ubicación:** `src/web/app.py:196-198`

**Código Problemático:**
```python
# Línea 196-198
session = loop.run_until_complete(
    conversation_memory.create_session(
        session_id=session_id,
        patient_info=patient_info  # ❌ UNDEFINED
    )
)
```

**Error:**
```python
NameError: name 'patient_info' is not defined
```

**Causa:** Copy-paste del endpoint `create_session`

**Fix Inmediato:**
```python
# ANTES (INCORRECTO):
@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_messages(session_id):
    try:
        limit = request.args.get("limit", type=int)

        loop = asyncio.get_event_loop()
        session = loop.run_until_complete(
            conversation_memory.create_session(  # ❌ WRONG
                session_id=session_id,
                patient_info=patient_info  # ❌ UNDEFINED
            )
        )
        ...

# DESPUÉS (CORRECTO):
@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_messages(session_id):
    try:
        limit = request.args.get("limit", default=50, type=int)

        loop = asyncio.get_event_loop()
        messages = loop.run_until_complete(
            conversation_memory.get_messages(  # ✅ CORRECT
                session_id=UUID(session_id),
                limit=limit
            )
        )

        return jsonify({
            "success": True,
            "messages": [msg.to_dict() for msg in messages]
        })

    except Exception as e:
        logger.error(f"❌ Error obteniendo mensajes: {e!s}")
        return jsonify({"success": False, "error": str(e)}), 500
```

**Esfuerzo:** 5 minutos
**Riesgo:** Ninguno
**Prioridad:** 🔴 URGENTE

---

#### **ISSUE #3: Checkpointer No Persistente**

**Ubicación:** `src/graph/medical_graph.py:126-154`

**Problema:**
```python
def create_memory_checkpointer() -> MemorySaver:
    """
    Crea el checkpointer en memoria para persistencia temporal.

    Note:
        Usando MemorySaver temporalmente. Para producción con PostgreSQL,
        instalar: pip install langgraph-checkpoint-postgres
        y usar AsyncPostgresSaver
    """
    logger.warning(
        "⚠️ [Checkpointer] Usando persistencia en memoria. "
        "Los checkpoints se perderán al reiniciar."
    )

    checkpointer = MemorySaver()
    return checkpointer
```

**Impacto:**
- 🔴 Estado del grafo se pierde al reiniciar
- No hay recuperación de sesiones
- Imposible escalar horizontalmente

**Solución:**
```bash
# 1. Instalar dependencia
uv add langgraph-checkpoint-postgres

# 2. Implementar AsyncPostgresSaver
```

```python
# src/graph/medical_graph.py (NUEVO)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from src.config.settings import settings

async def create_postgres_checkpointer() -> AsyncPostgresSaver:
    """
    Crea el checkpointer con PostgreSQL para persistencia real.

    Returns:
        AsyncPostgresSaver configurado
    """
    try:
        logger.info("ℹ️ [Checkpointer] Inicializando PostgreSQL saver")

        checkpointer = AsyncPostgresSaver.from_conn_string(
            settings.DATABASE_URL
        )

        # Inicializar tablas si no existen
        await checkpointer.setup()

        logger.info("✅ [Checkpointer] PostgreSQL saver inicializado")
        return checkpointer

    except Exception as e:
        logger.error(f"❌ [Checkpointer] Error: {e!s}")
        raise

# Actualizar create_medical_graph()
async def create_medical_graph() -> StateGraph:
    # ... código existente ...

    # Crear checkpointer persistente
    checkpointer = await create_postgres_checkpointer()

    # Compilar el grafo con checkpointer
    graph = workflow.compile(checkpointer=checkpointer)

    return graph
```

**Esfuerzo:** 4-6 horas
**Riesgo:** Medio
**Beneficio:** ⭐⭐⭐⭐⭐

---

#### **ISSUE #4: Sin Autenticación ni Autorización**

**Ubicación:** Todo el proyecto

**Problema:**
- Cualquiera puede crear sesiones
- Sin control de acceso a datos médicos sensibles
- No hay rate limiting por usuario
- Sin auditoría de accesos

**Riesgos de Seguridad:**
```
🔓 Sin autenticación:
├── Acceso anónimo a datos médicos
├── Abuso de API (spam de sesiones)
└── Sin trazabilidad de acciones

🔓 Sin autorización:
├── Cualquier usuario ve cualquier sesión
├── Sin roles (paciente, doctor, admin)
└── Sin permisos granulares

🔓 Sin encriptación:
├── patient_info en texto plano
├── Mensajes médicos sin encriptar
└── Datos sensibles en logs
```

**Solución Propuesta:**

**Fase 1: Autenticación Básica (JWT)**
```python
# pyproject.toml
dependencies = [
    # ... existentes ...
    "python-jose[cryptography]==3.3.0",  # JWT
    "passlib[bcrypt]==1.7.4",            # Password hashing
]

# src/models/user.py (NUEVO)
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"

@dataclass
class User:
    user_id: UUID
    email: str
    hashed_password: str
    full_name: str
    role: UserRole
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

# src/services/auth_service.py (NUEVO)
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"])
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30

    def verify_password(self, plain: str, hashed: str) -> bool:
        return self.pwd_context.verify(plain, hashed)

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def create_access_token(
        self,
        user_id: UUID,
        role: UserRole
    ) -> str:
        expire = datetime.utcnow() + timedelta(
            minutes=self.access_token_expire_minutes
        )
        to_encode = {
            "sub": str(user_id),
            "role": role.value,
            "exp": expire
        }
        return jwt.encode(to_encode, self.secret_key, self.algorithm)

    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except JWTError:
            raise ValueError("Invalid token")
```

**Fase 2: Middleware de Autenticación (FastAPI)**
```python
# src/web/middleware/auth.py (NUEVO)
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    token = credentials.credentials
    try:
        payload = auth_service.verify_token(token)
        user = await db_service.get_user(UUID(payload["sub"]))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        return user
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

# Uso en endpoints:
@app.post("/api/sessions")
async def create_session(
    patient_info: dict,
    current_user: User = Depends(get_current_user)  # ✅ Protegido
):
    # Solo usuarios autenticados pueden crear sesiones
    session = await conversation_memory.create_session(
        session_id=uuid4(),
        patient_info=patient_info,
        user_id=current_user.user_id  # Asociar a usuario
    )
    return {"session_id": str(session.session_id)}
```

**Esfuerzo:** 3-5 días
**Riesgo:** Medio
**Prioridad:** 🔴 CRÍTICA (datos médicos sensibles)

---

#### **ISSUE #5: Datos Médicos Sin Encriptación**

**Ubicación:** `src/services/database_service.py`, `src/models/session.py`

**Problema:**
```python
# Actualmente (INSEGURO):
await conn.execute(
    """
    INSERT INTO sessions (
        session_id, patient_info, metadata, is_active
    ) VALUES ($1, $2, $3, $4)
    """,
    session.session_id,
    json.dumps(session.patient_info),  # ❌ TEXTO PLANO
    json.dumps(session.metadata),      # ❌ TEXTO PLANO
    session.is_active,
)
```

**Riesgos:**
- 🔓 Datos médicos legibles en DB
- 🔓 Backups sin encriptar
- 🔓 Logs pueden contener PII
- ⚖️ Incumplimiento GDPR/HIPAA

**Solución: Encriptación a Nivel de Aplicación**

```python
# src/services/encryption_service.py (NUEVO)
from cryptography.fernet import Fernet
from src.config.settings import settings
import json

class EncryptionService:
    """Servicio de encriptación para datos sensibles."""

    def __init__(self):
        # IMPORTANTE: En producción, usar key management (AWS KMS, Vault)
        self.cipher = Fernet(settings.ENCRYPTION_KEY.encode())

    def encrypt_dict(self, data: dict) -> str:
        """Encripta un diccionario y retorna string encriptado."""
        json_str = json.dumps(data)
        encrypted = self.cipher.encrypt(json_str.encode())
        return encrypted.decode()

    def decrypt_dict(self, encrypted: str) -> dict:
        """Desencripta un string y retorna el diccionario original."""
        decrypted = self.cipher.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())

    def encrypt_string(self, text: str) -> str:
        """Encripta un string."""
        encrypted = self.cipher.encrypt(text.encode())
        return encrypted.decode()

    def decrypt_string(self, encrypted: str) -> str:
        """Desencripta un string."""
        decrypted = self.cipher.decrypt(encrypted.encode())
        return decrypted.decode()

# Instancia global
encryption_service = EncryptionService()

# src/services/database_service.py (MODIFICADO)
async def create_session(self, session: Session) -> Session:
    """Crea una nueva sesión con datos encriptados."""
    async with self.get_connection() as conn:
        # Encriptar datos sensibles
        encrypted_patient_info = encryption_service.encrypt_dict(
            session.patient_info
        )
        encrypted_metadata = encryption_service.encrypt_dict(
            session.metadata
        )

        await conn.execute(
            """
            INSERT INTO sessions (
                session_id, patient_info, metadata, is_active
            ) VALUES ($1, $2, $3, $4)
            """,
            session.session_id,
            encrypted_patient_info,  # ✅ ENCRIPTADO
            encrypted_metadata,      # ✅ ENCRIPTADO
            session.is_active,
        )
        logger.info(f"ℹ️ Sesión {session.session_id} creada (encriptada)")
        return session

async def get_session(self, session_id: UUID) -> Optional[Session]:
    """Obtiene una sesión y desencripta los datos."""
    async with self.get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE session_id = $1",
            session_id
        )

        if row:
            session_dict = dict(row)
            # Desencriptar datos
            session_dict["patient_info"] = encryption_service.decrypt_dict(
                session_dict["patient_info"]
            )
            session_dict["metadata"] = encryption_service.decrypt_dict(
                session_dict["metadata"]
            )
            return Session.from_dict(session_dict)
        return None

# src/config/settings.py (AGREGAR)
class Settings(BaseSettings):
    # ... campos existentes ...

    ENCRYPTION_KEY: str = Field(
        ...,
        description="Fernet encryption key (32 url-safe base64 bytes)"
    )

    @validator("ENCRYPTION_KEY")
    def validate_encryption_key(cls, v):
        """Valida que la key sea válida para Fernet."""
        try:
            Fernet(v.encode())
        except Exception:
            raise ValueError(
                "ENCRYPTION_KEY debe ser una key válida de Fernet. "
                "Generar con: python -c 'from cryptography.fernet "
                "import Fernet; print(Fernet.generate_key().decode())'"
            )
        return v
```

**Generación de Key:**
```bash
# .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Ejemplo: ENCRYPTION_KEY=bF3aH7kL9mN2pQ4sT6vX8zA1cD3fG5hJ7kM9nP2qR4s=
```

**Esfuerzo:** 1-2 días
**Riesgo:** Medio
**Prioridad:** 🔴 CRÍTICA (compliance)

---

### 🟡 IMPORTANTES - Mejoran Significativamente

#### **ISSUE #6: Sin Circuit Breaker en LLMService**

**Ubicación:** `src/services/llm_service.py`

**Problema:**
```python
# Actualmente solo hay retry (línea 25):
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((OpenAIError, asyncio.TimeoutError)),
)
async def complete(self, ...):
    # Si OpenAI está caído, reintenta 3 veces
    # Pero NO previene cascada de fallos
```

**Riesgos:**
- Cascada de fallos si OpenAI tiene outage
- Workers bloqueados esperando timeouts
- Costos acumulados de reintentos
- UX degradada sin fallback

**Solución: Circuit Breaker Pattern**

```python
# pyproject.toml
dependencies = [
    # ... existentes ...
    "pybreaker==1.0.1",  # Circuit breaker
]

# src/services/llm_service.py (MODIFICADO)
from pybreaker import CircuitBreaker, CircuitBreakerError
from typing import Optional

class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Circuit Breaker configuration
        self.circuit_breaker = CircuitBreaker(
            fail_max=5,              # Abre después de 5 fallos
            timeout_duration=60,     # Permanece abierto 60s
            exclude=[ValueError],    # No cuenta errores de validación
            name="openai_circuit"
        )

        logger.info("✅ LLMService inicializado con Circuit Breaker")

    @retry(...)  # Mantener retry
    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Completa un chat con circuit breaker.

        Raises:
            CircuitBreakerError: Si el circuit breaker está abierto
        """
        try:
            # Llamar a través del circuit breaker
            return await self.circuit_breaker.call_async(
                self._do_completion,
                messages,
                temperature,
                max_tokens
            )
        except CircuitBreakerError:
            logger.error("⚠️ Circuit breaker ABIERTO - OpenAI no disponible")
            # Fallback: respuesta predefinida
            return self._get_fallback_response()

    async def _do_completion(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ejecución real de la completion."""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.OPENAI_TIMEOUT,
        )
        return response.choices[0].message.content

    def _get_fallback_response(self) -> str:
        """Respuesta de fallback cuando el servicio está caído."""
        return (
            "Lo siento, estoy experimentando problemas técnicos temporales. "
            "Por favor, intenta nuevamente en unos minutos o contacta a "
            "un profesional médico directamente si es urgente."
        )

    def get_circuit_status(self) -> dict:
        """Estado del circuit breaker para observabilidad."""
        return {
            "state": self.circuit_breaker.current_state,
            "failure_count": self.circuit_breaker.fail_counter,
            "last_failure": self.circuit_breaker.last_failure,
        }
```

**Beneficios:**
- ✅ Previene cascada de fallos
- ✅ Recuperación automática (timeout)
- ✅ Fallback graceful
- ✅ Observabilidad del estado

**Esfuerzo:** 3-4 horas
**Riesgo:** Bajo
**Beneficio:** ⭐⭐⭐⭐

---

#### **ISSUE #7: Sin Caché de Respuestas LLM**

**Problema:**
- Consultas repetidas cuestan dinero
- Latencia innecesaria para preguntas comunes
- Sin aprovechar respuestas previas

**Ejemplo:**
```
Usuario 1: "¿Qué es la diabetes?"
→ Llamada a GPT-5.1 ($$$)

Usuario 2 (5 min después): "¿Qué es la diabetes?"
→ Llamada a GPT-5.1 otra vez ($$$)  ❌

Con cache:
→ Respuesta instantánea desde Redis (gratis) ✅
```

**Solución: Cache con Redis**

```python
# docker/docker-compose.yml (AGREGAR)
services:
  # ... postgres, app existentes ...

  redis:
    image: redis:7-alpine
    container_name: medical-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - medical-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

volumes:
  # ... existentes ...
  redis_data:
    driver: local

# pyproject.toml
dependencies = [
    # ... existentes ...
    "redis[hiredis]==5.0.1",  # Redis client optimizado
]

# src/services/cache_service.py (NUEVO)
import hashlib
import json
from typing import Optional
from redis.asyncio import Redis
from src.config.settings import settings

class CacheService:
    """Servicio de cache para respuestas LLM."""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.default_ttl = 3600  # 1 hora

    async def connect(self):
        """Conecta a Redis."""
        self.redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        logger.info("✅ Cache service conectado a Redis")

    async def disconnect(self):
        """Desconecta de Redis."""
        if self.redis:
            await self.redis.close()

    def _generate_cache_key(self, messages: list[dict]) -> str:
        """Genera key única basada en el contenido."""
        content = json.dumps(messages, sort_keys=True)
        hash_obj = hashlib.sha256(content.encode())
        return f"llm_cache:{hash_obj.hexdigest()}"

    async def get_cached_response(
        self,
        messages: list[dict]
    ) -> Optional[str]:
        """Obtiene respuesta cacheada si existe."""
        if not self.redis:
            return None

        key = self._generate_cache_key(messages)
        cached = await self.redis.get(key)

        if cached:
            logger.info(f"✅ Cache HIT para key: {key[:16]}...")
            return cached

        logger.debug(f"ℹ️ Cache MISS para key: {key[:16]}...")
        return None

    async def cache_response(
        self,
        messages: list[dict],
        response: str,
        ttl: Optional[int] = None
    ):
        """Cachea una respuesta."""
        if not self.redis:
            return

        key = self._generate_cache_key(messages)
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            response
        )
        logger.debug(f"✅ Respuesta cacheada: {key[:16]}...")

# Instancia global
cache_service = CacheService()

# src/services/llm_service.py (MODIFICADO)
async def complete(
    self,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    use_cache: bool = True,  # ✅ NUEVO
) -> str:
    """Completa un chat con cache opcional."""

    # Intentar obtener de cache
    if use_cache and temperature == 0:  # Solo cachear respuestas deterministas
        cached = await cache_service.get_cached_response(messages)
        if cached:
            return cached

    # Si no hay cache, llamar a OpenAI
    try:
        response = await self.circuit_breaker.call_async(
            self._do_completion,
            messages,
            temperature,
            max_tokens
        )

        # Cachear respuesta si es determinista
        if use_cache and temperature == 0:
            await cache_service.cache_response(messages, response)

        return response

    except CircuitBreakerError:
        return self._get_fallback_response()
```

**Configuración:**
```python
# src/config/settings.py
class Settings(BaseSettings):
    # ... existentes ...

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL de conexión a Redis"
    )

    CACHE_ENABLED: bool = Field(default=True)
    CACHE_TTL: int = Field(default=3600, description="TTL en segundos")
```

**Beneficios:**
- 💰 Reduce costos de API (hasta 40-60% para preguntas comunes)
- ⚡ Respuestas instantáneas (< 10ms vs 2-5s)
- 📊 Métricas de cache hit rate

**Esfuerzo:** 1 día
**Riesgo:** Bajo
**Beneficio:** ⭐⭐⭐⭐

---

#### **ISSUE #8: Cobertura de Tests <20%**

**Ubicación:** `tests/`

**Problema:**
```bash
$ pytest --cov=src
---------- coverage: platform linux, python 3.11.9 -----------
Name                              Stmts   Miss  Cover
-----------------------------------------------------
src/agents/base_agent.py             45     38    16%
src/agents/triage_agent.py           67     58    13%
src/services/database_service.py     89     76    15%
src/web/app.py                      156    142     9%
-----------------------------------------------------
TOTAL                               3597   3102    14%
```

**Riesgos:**
- Regresiones no detectadas
- Refactorización arriesgada
- Bugs en producción
- Confianza baja en despliegues

**Plan de Testing:**

**Fase 1: Tests Unitarios (Objetivo: 70%)**
```python
# tests/test_agents.py (EXPANDIR)
import pytest
from uuid import uuid4
from src.agents.specialists.cardiology import CardiologyAgent
from src.services.llm_service import llm_service

class TestCardiologyAgent:
    @pytest.fixture
    def agent(self):
        return CardiologyAgent(llm_service)

    @pytest.mark.asyncio
    async def test_evaluate_relevant_case(self, agent):
        """Test evaluación de caso cardiovascular relevante."""
        messages = [
            {
                "role": "user",
                "content": "Tengo dolor en el pecho y dificultad para respirar"
            }
        ]

        evaluation = await agent.evaluate(messages)

        assert evaluation.specialist_type == "cardiology"
        assert evaluation.relevance_score >= 80
        assert "dolor" in evaluation.reasoning.lower()
        assert len(evaluation.key_symptoms) > 0

    @pytest.mark.asyncio
    async def test_evaluate_irrelevant_case(self, agent):
        """Test evaluación de caso no cardiovascular."""
        messages = [
            {
                "role": "user",
                "content": "Tengo sarpullido en la piel"
            }
        ]

        evaluation = await agent.evaluate(messages)

        assert evaluation.relevance_score < 50
        assert "piel" not in " ".join(evaluation.key_symptoms)

# tests/test_services.py (NUEVO)
import pytest
from src.services.database_service import db_service
from src.models.session import Session
from uuid import uuid4

class TestDatabaseService:
    @pytest.mark.asyncio
    async def test_create_and_get_session(self):
        """Test crear y recuperar sesión."""
        session_id = uuid4()
        patient_info = {"name": "Test Patient", "age": 30}

        # Crear
        session = Session(
            session_id=session_id,
            patient_info=patient_info
        )
        await db_service.create_session(session)

        # Recuperar
        retrieved = await db_service.get_session(session_id)

        assert retrieved is not None
        assert retrieved.session_id == session_id
        assert retrieved.patient_info == patient_info

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self):
        """Test añadir y recuperar mensajes."""
        # ... implementar ...

# tests/test_graph.py (EXPANDIR)
import pytest
from src.graph.medical_graph import medical_graph_manager
from src.graph.state import MedicalGraphState
from src.models.message import Message

class TestMedicalGraph:
    @pytest.mark.asyncio
    async def test_full_triage_flow(self):
        """Test flujo completo de triaje."""
        session_id = uuid4()
        message = Message(
            role="user",
            content="Tengo fiebre y tos desde hace 3 días",
            session_id=session_id
        )

        state = MedicalGraphState(
            session_id=session_id,
            thread_id=f"thread_{session_id}",
            messages=[message]
        )

        config = {"configurable": {"thread_id": state.thread_id}}

        result = await medical_graph_manager.invoke(state, config)

        assert result.triage_completed
        assert result.selected_specialist is not None
        assert len(result.evaluations) == 8  # Todos los especialistas

    @pytest.mark.asyncio
    async def test_parallel_evaluation(self):
        """Test evaluación paralela de especialistas."""
        # ... implementar ...
```

**Fase 2: Tests de Integración**
```python
# tests/integration/test_api.py (NUEVO)
import pytest
from httpx import AsyncClient
from src.web.app import app

class TestAPIIntegration:
    @pytest.mark.asyncio
    async def test_create_session_endpoint(self):
        """Test endpoint de creación de sesión."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/sessions",
                json={"patient_info": {"name": "Test", "age": 25}}
            )

            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data
            assert "thread_id" in data

    @pytest.mark.asyncio
    async def test_websocket_flow(self):
        """Test flujo completo via WebSocket."""
        # ... implementar con pytest-asyncio y websockets ...
```

**Fase 3: Mocking de LLM**
```python
# tests/conftest.py (NUEVO)
import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_service():
    """Mock del servicio LLM para tests deterministas."""
    with patch("src.services.llm_service.llm_service") as mock:
        # Response predefinida para triaje
        mock.complete_json.return_value = {
            "urgency_level": "medium",
            "symptoms": ["fever", "cough"],
            "recommended_specialties": ["general_medicine"],
            "requires_immediate_attention": False
        }

        # Response predefinida para evaluación
        mock.complete.return_value = (
            "Este caso requiere atención de medicina general "
            "debido a los síntomas respiratorios presentados."
        )

        yield mock

# Uso en tests:
@pytest.mark.asyncio
async def test_triage_with_mock(mock_llm_service):
    agent = TriageAgent(mock_llm_service)
    result = await agent.evaluate([...])
    assert result.urgency_level == "medium"
```

**Meta de Cobertura:**
```
Fase 1 (2 semanas):    40% → 70%
Fase 2 (1 semana):     70% → 80%
Fase 3 (ongoing):      80% → 90%
```

**Esfuerzo:** 2-3 semanas
**Riesgo:** Bajo
**Beneficio:** ⭐⭐⭐⭐⭐

---

### 🟢 MEJORAS OPCIONALES - Nice to Have

#### **ISSUE #9: Observabilidad Limitada**

**Problema:**
- No hay métricas de negocio
- Sin tracing distribuido
- Logs no estructurados
- Dificulta debugging en producción

**Solución: Observabilidad Completa**

```python
# pyproject.toml
dependencies = [
    # ... existentes ...
    "prometheus-client==0.19.0",     # Métricas
    "opentelemetry-api==1.22.0",     # Tracing
    "opentelemetry-sdk==1.22.0",
    "opentelemetry-instrumentation-fastapi==0.43b0",
    "structlog==24.1.0",             # Logging estructurado
]

# src/services/metrics_service.py (NUEVO)
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

class MetricsService:
    def __init__(self):
        # Contadores
        self.sessions_created = Counter(
            "medical_sessions_created_total",
            "Total de sesiones creadas"
        )

        self.messages_processed = Counter(
            "medical_messages_processed_total",
            "Total de mensajes procesados",
            ["specialist_type"]
        )

        self.llm_calls = Counter(
            "medical_llm_calls_total",
            "Total de llamadas a LLM",
            ["model", "status"]
        )

        # Histogramas (latencia)
        self.triage_duration = Histogram(
            "medical_triage_duration_seconds",
            "Duración del triaje en segundos"
        )

        self.specialist_evaluation_duration = Histogram(
            "medical_evaluation_duration_seconds",
            "Duración de evaluación por especialista",
            ["specialist_type"]
        )

        self.response_duration = Histogram(
            "medical_response_duration_seconds",
            "Duración total de respuesta"
        )

        # Gauges (estado actual)
        self.active_sessions = Gauge(
            "medical_active_sessions",
            "Sesiones activas actualmente"
        )

        self.circuit_breaker_state = Gauge(
            "medical_circuit_breaker_open",
            "Estado del circuit breaker (1=abierto, 0=cerrado)"
        )

    def export_metrics(self) -> bytes:
        """Exporta métricas en formato Prometheus."""
        return generate_latest()

# Instancia global
metrics = MetricsService()

# src/web/app.py (AGREGAR ENDPOINT)
@app.get("/metrics")
async def prometheus_metrics():
    """Endpoint de métricas para Prometheus."""
    return Response(
        content=metrics.export_metrics(),
        media_type="text/plain"
    )

# Uso en el código:
# src/graph/nodes.py
async def triage_node(state: MedicalGraphState) -> dict:
    start_time = time.time()

    try:
        result = await triage_agent.evaluate(...)

        # Registrar métrica
        duration = time.time() - start_time
        metrics.triage_duration.observe(duration)

        return result
    except Exception as e:
        metrics.llm_calls.labels(model="gpt-5.1", status="error").inc()
        raise
```

**Logging Estructurado:**
```python
# src/utils/logging_config.py (MODIFICAR)
import structlog
from structlog.stdlib import LoggerFactory

def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=LoggerFactory(),
    )

# Uso:
logger = structlog.get_logger()
logger.info(
    "session_created",
    session_id=str(session_id),
    patient_age=patient_info.get("age"),
    specialist="cardiology"
)

# Output (JSON para parsing fácil):
# {
#   "event": "session_created",
#   "level": "info",
#   "timestamp": "2025-12-28T10:30:45.123Z",
#   "session_id": "123e4567-e89b-12d3-a456-426614174000",
#   "patient_age": 45,
#   "specialist": "cardiology"
# }
```

**Grafana Dashboard:**
```yaml
# docker/grafana/dashboards/medical_system.json
{
  "dashboard": {
    "title": "Medical System Metrics",
    "panels": [
      {
        "title": "Sessions Created (rate)",
        "targets": [
          {
            "expr": "rate(medical_sessions_created_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time p95",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, medical_response_duration_seconds)"
          }
        ]
      },
      {
        "title": "LLM Calls by Status",
        "targets": [
          {
            "expr": "sum(medical_llm_calls_total) by (status)"
          }
        ]
      }
    ]
  }
}
```

**Esfuerzo:** 3-5 días
**Beneficio:** ⭐⭐⭐⭐ (crítico para producción)

---

## 🚀 PLAN DE MIGRACIÓN A FASTAPI (DETALLADO)

### ¿Por Qué FastAPI?

**Comparación Flask vs FastAPI:**

| Aspecto | Flask + eventlet | FastAPI + uvicorn | Ganancia |
|---------|------------------|-------------------|----------|
| **Async Support** | Monkey-patching | Native async/await | ⭐⭐⭐⭐⭐ |
| **Performance** | ~1000 req/s | ~3000-4000 req/s | 3-4x |
| **WebSocket** | flask-socketio | Native | Sin conflictos |
| **Event Loop** | eventlet conflicts | asyncio nativo | Resuelve ISSUE #1 |
| **Validación** | Manual | Pydantic auto | DX mejorado |
| **Documentación** | Manual | OpenAPI auto | Swagger UI gratis |
| **Type Hints** | Opcional | Requerido | Mejor IDE support |
| **Async DB** | Problemas (asyncpg) | Funciona perfecto | ✅ |

**Decisión:** ⭐ **FastAPI es la opción correcta**

---

### Fase 1: Preparación (Día 0 - 4 horas)

#### 1.1. Backup y Branch

```bash
# 1. Crear branch de migración
git checkout -b feature/fastapi-migration

# 2. Backup de archivos clave
cp src/web/app.py src/web/app_flask_backup.py
cp docker/docker-compose.yml docker/docker-compose.flask.yml

# 3. Commit estado actual
git add .
git commit -m "chore: backup before FastAPI migration"
```

#### 1.2. Instalar Dependencias

```bash
# pyproject.toml (MODIFICAR)
dependencies = [
    # REMOVER:
    # "flask[async]==3.1.0",
    # "flask-cors==5.0.0",
    # "flask-socketio==5.4.1",
    # "python-socketio==5.12.0",
    # "eventlet==0.37.0",
    # "gunicorn==23.0.0",

    # AGREGAR:
    "fastapi[all]==0.108.0",        # Framework + extras
    "uvicorn[standard]==0.25.0",    # ASGI server
    "python-multipart==0.0.6",      # Form data
    "websockets==12.0",             # WebSocket support

    # LangGraph y otros (MANTENER)
    "langgraph==0.2.45",
    "langchain==0.3.10",
    # ... resto igual ...
]

# Instalar
uv sync
```

#### 1.3. Crear Estructura FastAPI

```bash
# Nueva estructura:
src/web/
├── app_flask_backup.py      # Backup
├── main.py                   # ✅ NUEVO: FastAPI app
├── routers/                  # ✅ NUEVO: Endpoints organizados
│   ├── __init__.py
│   ├── sessions.py          # POST /api/sessions, GET /api/sessions/{id}
│   ├── messages.py          # GET /api/sessions/{id}/messages
│   └── health.py            # GET /health, GET /metrics
├── websocket/               # ✅ NUEVO: WebSocket handlers
│   ├── __init__.py
│   └── chat.py              # WebSocket /ws/{session_id}
├── middleware/              # ✅ NUEVO: Middleware
│   ├── __init__.py
│   ├── auth.py              # Autenticación
│   └── cors.py              # CORS config
├── templates/               # Mantener
│   ├── base.html
│   └── index.html
└── static/                  # Mantener
    ├── css/
    └── js/
```

---

### Fase 2: Implementación (Día 1 - 8 horas)

#### 2.1. Aplicación Principal

```python
# src/web/main.py (NUEVO)
"""
Aplicación FastAPI para el sistema médico.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.config.settings import settings
from src.graph.medical_graph import medical_graph_manager
from src.services.database_service import db_service
from src.services.cache_service import cache_service
from src.utils.logging_config import setup_logging
from src.web.routers import sessions, messages, health
from src.web.websocket import chat

import logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager para startup y shutdown.
    """
    # Startup
    logger.info("🚀 Iniciando Medical Center API")

    # Inicializar servicios
    await db_service.connect()
    await cache_service.connect()
    await medical_graph_manager.initialize()

    logger.info("✅ Servicios inicializados")

    yield

    # Shutdown
    logger.info("👋 Cerrando Medical Center API")
    await db_service.disconnect()
    await cache_service.disconnect()
    logger.info("✅ Servicios cerrados")


# Crear aplicación
app = FastAPI(
    title="LangGraph Medical Center API",
    description="Sistema de agentes médicos especializados con LangGraph",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])
app.include_router(messages.router, prefix="/api", tags=["Messages"])
app.include_router(chat.router, tags=["WebSocket"])

# Static files
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

# Templates
templates = Jinja2Templates(directory="src/web/templates")


@app.get("/")
async def index(request: Request):
    """Página principal."""
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.web.main:app",
        host=settings.FLASK_HOST,
        port=settings.FLASK_PORT,
        reload=settings.FLASK_DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
```

#### 2.2. Router de Sesiones

```python
# src/web/routers/sessions.py (NUEVO)
"""
Endpoints para gestión de sesiones.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import Optional

from src.memory.conversation_memory import conversation_memory
from src.models.session import Session

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Request para crear sesión."""
    patient_info: dict = Field(
        ...,
        example={"name": "Juan Pérez", "age": 45, "gender": "M"}
    )


class SessionResponse(BaseModel):
    """Response de sesión creada."""
    success: bool
    session_id: str
    thread_id: str


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Crea una nueva sesión de conversación.

    Args:
        request: Datos del paciente

    Returns:
        SessionResponse con session_id y thread_id
    """
    try:
        session_id = uuid4()

        # Crear sesión en base de datos
        session = await conversation_memory.create_session(
            session_id=session_id,
            patient_info=request.patient_info
        )

        logger.info(f"ℹ️ [API] Sesión creada: {session_id}")

        return SessionResponse(
            success=True,
            session_id=str(session_id),
            thread_id=f"thread_{session_id}"
        )

    except Exception as e:
        logger.error(f"❌ [API] Error creando sesión: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID):
    """
    Obtiene información de una sesión.

    Args:
        session_id: ID de la sesión

    Returns:
        Datos de la sesión
    """
    try:
        session = await conversation_memory.get_session(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        summary = await conversation_memory.get_conversation_summary(session_id)

        return {
            "success": True,
            "session": session.to_dict(),
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [API] Error obteniendo sesión: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

#### 2.3. Router de Mensajes

```python
# src/web/routers/messages.py (NUEVO)
"""
Endpoints para gestión de mensajes.
"""
from fastapi import APIRouter, HTTPException, Query
from uuid import UUID
from typing import Optional

from src.memory.conversation_memory import conversation_memory

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: UUID,
    limit: Optional[int] = Query(default=50, ge=1, le=500)
):
    """
    Obtiene mensajes de una sesión.

    Args:
        session_id: ID de la sesión
        limit: Número máximo de mensajes a retornar

    Returns:
        Lista de mensajes
    """
    try:
        messages = await conversation_memory.get_messages(
            session_id=session_id,
            limit=limit
        )

        return {
            "success": True,
            "count": len(messages),
            "messages": [msg.to_dict() for msg in messages]
        }

    except Exception as e:
        logger.error(f"❌ [API] Error obteniendo mensajes: {e!s}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
```

#### 2.4. WebSocket Handler

```python
# src/web/websocket/chat.py (NUEVO)
"""
WebSocket handler para chat en tiempo real.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID
import logging

from src.graph.medical_graph import medical_graph_manager
from src.graph.state import MedicalGraphState
from src.models.message import Message
from src.memory.conversation_memory import conversation_memory

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Gestor de conexiones WebSocket activas."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Conecta un cliente."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"ℹ️ [WebSocket] Cliente conectado: {session_id}")

    def disconnect(self, session_id: str):
        """Desconecta un cliente."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"ℹ️ [WebSocket] Cliente desconectado: {session_id}")

    async def send_json(self, session_id: str, data: dict):
        """Envía datos JSON a un cliente."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint para chat en tiempo real.

    Args:
        websocket: Conexión WebSocket
        session_id: ID de la sesión
    """
    await manager.connect(session_id, websocket)

    try:
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_json()

            message_content = data.get("message")
            if not message_content:
                await manager.send_json(session_id, {
                    "type": "error",
                    "message": "Message content required"
                })
                continue

            logger.info(f"ℹ️ [WebSocket] Mensaje recibido: {session_id}")

            # Procesar mensaje
            await process_user_message(
                session_id=session_id,
                message_content=message_content,
                manager=manager
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"❌ [WebSocket] Error: {e!s}")
        await manager.send_json(session_id, {
            "type": "error",
            "message": str(e)
        })
        manager.disconnect(session_id)


async def process_user_message(
    session_id: str,
    message_content: str,
    manager: ConnectionManager
):
    """
    Procesa un mensaje del usuario y ejecuta el grafo.

    Args:
        session_id: ID de la sesión
        message_content: Contenido del mensaje
        manager: Gestor de conexiones
    """
    try:
        # Crear mensaje del usuario
        user_message = Message(
            role="user",
            content=message_content,
            session_id=UUID(session_id)
        )

        # Guardar mensaje ✅ SIN CONFLICTOS DE EVENT LOOP
        await conversation_memory.add_message(user_message)

        # Crear estado inicial
        state = MedicalGraphState(
            session_id=UUID(session_id),
            thread_id=f"thread_{session_id}",
            messages=[user_message],
        )

        # Configuración para LangGraph
        config = {
            "configurable": {"thread_id": state.thread_id},
            "recursion_limit": 50,
        }

        # Indicar que está procesando
        await manager.send_json(session_id, {
            "type": "thinking",
            "agent_name": "Triaje"
        })

        logger.info("ℹ️ [WebSocket] Iniciando stream del grafo")

        # Ejecutar grafo en streaming ✅ ASYNC NATIVO
        async for event in medical_graph_manager.stream(state, config):
            node_name = next(iter(event.keys()))
            node_output = event[node_name]

            logger.info(f"ℹ️ [Graph] Nodo ejecutado: {node_name}")

            # Enviar actualización del grafo
            graph_data = {"type": "graph_update", "node": node_name}

            # Incluir evaluaciones si las hay
            if "evaluations" in node_output:
                evaluations_data = [
                    {
                        "specialist_type": eval.specialist_type,
                        "relevance_score": eval.relevance_score,
                        "reasoning": eval.reasoning,
                    }
                    for eval in node_output["evaluations"]
                ]
                graph_data["data"] = {"evaluations": evaluations_data}

            await manager.send_json(session_id, graph_data)

            # Enviar mensajes si los hay
            if "messages" in node_output:
                for msg in node_output["messages"]:
                    # Guardar mensaje ✅ FUNCIONA PERFECTO
                    await conversation_memory.add_message(msg)

                    # Enviar al frontend
                    await manager.send_json(session_id, {
                        "type": "agent_response",
                        "role": msg.role,
                        "content": msg.content,
                        "specialist_type": msg.specialist_type,
                        "metadata": msg.metadata,
                        "is_final": True,
                    })

        logger.info(f"✅ [WebSocket] Procesamiento completado: {session_id}")

    except Exception as e:
        logger.error(f"❌ [WebSocket] Error procesando mensaje: {e!s}")
        import traceback
        logger.error(traceback.format_exc())

        await manager.send_json(session_id, {
            "type": "error",
            "message": str(e)
        })
```

#### 2.5. Health Checks

```python
# src/web/routers/health.py (NUEVO)
"""
Endpoints de health checks y métricas.
"""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
import os

from src.services.database_service import db_service
from src.graph.medical_graph import medical_graph_manager
from src.services.metrics_service import metrics

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health():
    """
    Health check endpoint.

    Returns:
        Estado de salud del sistema
    """
    db_status = "ready"
    if db_service.pool:
        db_status = "connected"
    elif db_service._worker_pid != os.getpid():
        db_status = "pending (new worker)"
    else:
        db_status = "pending"

    return {
        "status": "healthy",
        "version": "2.0.0",
        "worker_pid": os.getpid(),
        "services": {
            "database": db_status,
            "llm": "configured",
            "graph": "initialized" if medical_graph_manager.graph else "pending",
        },
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Endpoint de métricas para Prometheus.

    Returns:
        Métricas en formato Prometheus
    """
    return metrics.export_metrics()
```

---

### Fase 3: Frontend (Día 1 - 2 horas)

#### 3.1. Actualizar JavaScript

```javascript
// src/web/static/js/main.js (MODIFICAR)

// ANTES (Flask-SocketIO):
const socket = io();

socket.on('connect', () => {
    console.log('Connected to server');
});

socket.emit('join_session', { session_id: sessionId });

socket.emit('user_message', {
    session_id: sessionId,
    message: userMessage
});

// DESPUÉS (FastAPI WebSocket):
let ws = null;

function connectWebSocket(sessionId) {
    ws = new WebSocket(`ws://localhost:5000/ws/${sessionId}`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        showStatus('Conectado');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showError('Error de conexión');
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
        showStatus('Desconectado');
    };
}

function sendMessage(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message: message }));
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'thinking':
            showThinking(data.agent_name);
            break;
        case 'graph_update':
            updateGraph(data.node, data.data);
            break;
        case 'agent_response':
            displayMessage(data);
            break;
        case 'error':
            showError(data.message);
            break;
    }
}

// Inicialización
async function init() {
    // Crear sesión
    const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            patient_info: {
                name: userName,
                age: userAge
            }
        })
    });

    const data = await response.json();
    const sessionId = data.session_id;

    // Conectar WebSocket
    connectWebSocket(sessionId);
}
```

---

### Fase 4: Docker y Deployment (Día 2 - 3 horas)

#### 4.1. Actualizar Dockerfile

```dockerfile
# docker/Dockerfile (MODIFICAR)

# Stage 1: Builder
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Copiar archivos de dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copiar código fuente
COPY . .

# Instalar proyecto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.11-slim-bookworm

# Usuario non-root
RUN useradd -m -u 1000 medical && \
    mkdir -p /app/logs && \
    chown -R medical:medical /app

WORKDIR /app

# Copiar entorno virtual desde builder
COPY --from=builder --chown=medical:medical /app/.venv /app/.venv
COPY --from=builder --chown=medical:medical /app /app

# Path
ENV PATH="/app/.venv/bin:$PATH"

# Usuario
USER medical

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Puerto
EXPOSE 5000

# Comando ✅ UVICORN en lugar de Gunicorn
CMD ["uvicorn", "src.web.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--log-level", "info"]
```

#### 4.2. Actualizar docker-compose.yml

```yaml
# docker/docker-compose.yml (MODIFICAR)

services:
  # ... postgres igual ...

  redis:  # ✅ NUEVO
    image: redis:7-alpine
    container_name: medical-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - medical-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru

  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: medical-app
    restart: unless-stopped
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: ${OPENAI_MODEL:-gpt-5.1}
      DATABASE_URL: postgresql://medical_user:medical_password@postgres:5432/medical_db
      REDIS_URL: redis://redis:6379/0  # ✅ NUEVO
      FLASK_HOST: 0.0.0.0  # Mantener nombre por compatibilidad
      FLASK_PORT: 5000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "5000:5000"
    volumes:
      - ../logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - medical-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # ... pgadmin igual ...

volumes:
  postgres_data:
  redis_data:  # ✅ NUEVO
  pgadmin_data:
```

---

### Fase 5: Testing (Día 2 - 3 horas)

#### 5.1. Tests de Migración

```python
# tests/test_fastapi_migration.py (NUEVO)
"""
Tests para validar la migración a FastAPI.
"""
import pytest
from httpx import AsyncClient
from src.web.main import app

class TestFastAPIMigration:
    """Tests de compatibilidad post-migración."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test endpoint de salud."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data

    @pytest.mark.asyncio
    async def test_create_session_endpoint(self):
        """Test creación de sesión (backward compatibility)."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/sessions",
                json={"patient_info": {"name": "Test", "age": 30}}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "session_id" in data
            assert "thread_id" in data

    @pytest.mark.asyncio
    async def test_get_session_endpoint(self):
        """Test obtener sesión."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Crear sesión
            create_resp = await client.post(
                "/api/sessions",
                json={"patient_info": {"name": "Test", "age": 30}}
            )
            session_id = create_resp.json()["session_id"]

            # Obtener sesión
            get_resp = await client.get(f"/api/sessions/{session_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["success"] is True
            assert "session" in data

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test conexión WebSocket."""
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/ws/test-session-id") as websocket:
                # Enviar mensaje
                websocket.send_json({"message": "Hello"})

                # Recibir respuesta (thinking)
                data = websocket.receive_json()
                assert data["type"] in ["thinking", "graph_update", "agent_response"]

    @pytest.mark.asyncio
    async def test_openapi_docs(self):
        """Test que la documentación OpenAPI esté disponible."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/docs")
            assert response.status_code == 200

            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "openapi" in schema
            assert "paths" in schema
```

#### 5.2. Script de Validación

```bash
#!/bin/bash
# tests/validate_migration.sh (NUEVO)

echo "🧪 Validando migración a FastAPI..."

# 1. Levantar servicios
cd docker
docker-compose up -d
sleep 10

# 2. Health check
echo "✅ Test 1: Health endpoint"
curl -f http://localhost:5000/health || exit 1

# 3. Crear sesión
echo "✅ Test 2: Crear sesión"
SESSION_RESPONSE=$(curl -s -X POST http://localhost:5000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"patient_info": {"name": "Test", "age": 30}}')

SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION_ID"

# 4. OpenAPI docs
echo "✅ Test 3: OpenAPI docs"
curl -f http://localhost:5000/docs || exit 1

# 5. Métricas
echo "✅ Test 4: Métricas Prometheus"
curl -f http://localhost:5000/metrics || exit 1

# 6. WebSocket (manual test)
echo "⚠️ Test 5: WebSocket (manual - abrir index.html en navegador)"

echo "✅ Todos los tests pasaron!"
```

---

### Fase 6: Documentación y Rollout (Día 3 - 2 horas)

#### 6.1. Actualizar README

```markdown
# README.md (ACTUALIZAR sección de tecnologías)

## 🏗️ Arquitectura del Sistema

**Stack Tecnológico v2.0:**
- ✅ **FastAPI** - Framework web moderno y async
- ✅ **Uvicorn** - ASGI server de alto rendimiento
- ✅ **PostgreSQL** - Base de datos principal
- ✅ **Redis** - Cache y message broker
- ✅ **LangGraph** - Orquestación de agentes
- ✅ **OpenAI GPT-5.1** - Modelo de lenguaje

**Mejoras en v2.0:**
- 🚀 3-4x mejor performance
- ✅ Soporte async nativo (sin conflictos)
- 📚 Auto-documentación OpenAPI
- 🔒 Persistencia de mensajes habilitada
- 📊 Métricas Prometheus integradas
- ⚡ Cache Redis para respuestas

## 🚀 Inicio Rápido

\`\`\`bash
# 1. Clonar repositorio
git clone <repo-url>
cd langgraph-medical-center

# 2. Configurar .env
cp .env.example .env
# Editar .env con tus credenciales

# 3. Levantar con Docker
cd docker
docker-compose up --build

# 4. Acceder
- UI: http://localhost:5000
- API Docs: http://localhost:5000/docs
- ReDoc: http://localhost:5000/redoc
- Metrics: http://localhost:5000/metrics
\`\`\`
```

#### 6.2. Migration Guide

```markdown
# FASTAPI_MIGRATION_GUIDE.md (NUEVO)

# 🔄 Guía de Migración Flask → FastAPI

## Cambios Principales

### 1. Framework
- **ANTES:** Flask 3.1.0 + Flask-SocketIO + eventlet
- **DESPUÉS:** FastAPI 0.108.0 + uvicorn + websockets nativo

### 2. Async Handling
- **ANTES:** `loop.run_until_complete()` (blocking)
- **DESPUÉS:** `await` nativo (non-blocking)

### 3. WebSocket
- **ANTES:** Socket.IO protocol con eventlet
- **DESPUÉS:** WebSocket nativo W3C standard

### 4. Validación
- **ANTES:** Manual con if/else
- **DESPUÉS:** Pydantic automático

## Breaking Changes

### API Endpoints (sin cambios)
Todos los endpoints mantienen backward compatibility:
- ✅ `POST /api/sessions`
- ✅ `GET /api/sessions/{id}`
- ✅ `GET /api/sessions/{id}/messages`
- ✅ `GET /health`

### WebSocket Protocol (cambios)

**ANTES (Socket.IO):**
\`\`\`javascript
socket.emit('user_message', { message: "..." });
socket.on('agent_response', (data) => {...});
\`\`\`

**DESPUÉS (WebSocket nativo):**
\`\`\`javascript
ws.send(JSON.stringify({ message: "..." }));
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'agent_response') {...}
};
\`\`\`

## Rollback Plan

Si hay problemas, rollback a Flask:

\`\`\`bash
# 1. Checkout a branch anterior
git checkout main  # o el tag de Flask

# 2. Rebuild Docker
cd docker
docker-compose down
docker-compose up --build

# 3. Verificar
curl http://localhost:5000/health
\`\`\`

## Beneficios Post-Migración

1. ✅ **Persistencia de mensajes habilitada** (ISSUE #1 resuelto)
2. ✅ **3-4x mejor performance**
3. ✅ **Auto-documentación** en `/docs`
4. ✅ **Métricas Prometheus** en `/metrics`
5. ✅ **Sin conflictos de event loop**
6. ✅ **Async DB operations** funcionando
7. ✅ **Type safety** mejorado
```

---

### Fase 7: Checklist de Migración

```markdown
## ✅ Checklist de Migración a FastAPI

### Preparación
- [ ] Crear branch `feature/fastapi-migration`
- [ ] Backup de `app.py` → `app_flask_backup.py`
- [ ] Backup de `docker-compose.yml`
- [ ] Commit estado actual

### Dependencias
- [ ] Agregar FastAPI, uvicorn, websockets a pyproject.toml
- [ ] Remover Flask, flask-socketio, eventlet
- [ ] `uv sync`
- [ ] Verificar lockfile (`uv.lock`)

### Código
- [ ] Crear `src/web/main.py` (FastAPI app)
- [ ] Crear `src/web/routers/sessions.py`
- [ ] Crear `src/web/routers/messages.py`
- [ ] Crear `src/web/routers/health.py`
- [ ] Crear `src/web/websocket/chat.py`
- [ ] Actualizar `src/web/static/js/main.js` (WebSocket)

### Docker
- [ ] Actualizar Dockerfile (uvicorn en vez de gunicorn)
- [ ] Agregar servicio Redis a docker-compose.yml
- [ ] Actualizar healthcheck
- [ ] Rebuild imagen

### Testing
- [ ] Ejecutar `pytest tests/test_fastapi_migration.py`
- [ ] Ejecutar `tests/validate_migration.sh`
- [ ] Test manual de WebSocket en navegador
- [ ] Verificar persistencia de mensajes
- [ ] Load testing (opcional)

### Documentación
- [ ] Actualizar README.md
- [ ] Crear FASTAPI_MIGRATION_GUIDE.md
- [ ] Actualizar KNOWN_ISSUES.md (remover ISSUE #1)
- [ ] Update API docs (automatic via /docs)

### Deployment
- [ ] Test en staging
- [ ] Smoke tests
- [ ] Merge a main
- [ ] Deploy a producción
- [ ] Monitor logs y métricas
- [ ] Verificar con usuarios

### Post-Deployment
- [ ] Eliminar código Flask legacy después de 1 semana
- [ ] Actualizar CI/CD pipelines
- [ ] Update team documentation
```

---

### Estimación de Esfuerzo

| Fase | Tiempo | Riesgo |
|------|--------|--------|
| **Fase 1: Preparación** | 4 horas | Bajo |
| **Fase 2: Implementación** | 8 horas | Medio |
| **Fase 3: Frontend** | 2 horas | Bajo |
| **Fase 4: Docker** | 3 horas | Bajo |
| **Fase 5: Testing** | 3 horas | Medio |
| **Fase 6: Docs** | 2 horas | Bajo |
| **TOTAL** | **22 horas** (~3 días) | **Medio** |

---

## 📅 ROADMAP DE MEJORAS (FASES)

### 🔴 Fase 1: Estabilización (Semanas 1-2)

**Objetivo:** Resolver issues críticos y preparar base sólida

**Issues a resolver:**
1. ✅ Migrar a FastAPI (ISSUE #1) - 3 días
2. ✅ Fix bug get_messages (ISSUE #2) - 5 min
3. ✅ AsyncPostgresSaver (ISSUE #3) - 4 horas
4. ✅ Encriptación patient_info (ISSUE #5) - 1 día
5. ✅ Tests básicos >40% cobertura - 3 días

**Entregables:**
- [ ] Sistema funcionando 100% (sin issues bloqueantes)
- [ ] Persistencia de mensajes habilitada
- [ ] Datos sensibles encriptados
- [ ] Tests básicos pasando
- [ ] Documentación actualizada

**Métricas de Éxito:**
- ✅ Uptime >99% en pruebas
- ✅ Latencia p95 < 3s
- ✅ Sin errores de event loop
- ✅ Cobertura tests >40%

---

### 🟡 Fase 2: Seguridad y Resiliencia (Semanas 3-4)

**Objetivo:** Sistema seguro y robusto para producción

**Features:**
1. ✅ Autenticación JWT (ISSUE #4) - 2 días
2. ✅ Autorización role-based - 1 día
3. ✅ Circuit Breaker (ISSUE #6) - 4 horas
4. ✅ Cache Redis (ISSUE #7) - 1 día
5. ✅ Rate limiting - 3 horas
6. ✅ Input validation robusta - 4 horas

**Entregables:**
- [ ] Sistema con autenticación completa
- [ ] Roles: patient, doctor, admin
- [ ] Circuit breaker en LLMService
- [ ] Cache Redis operativo
- [ ] Rate limiting por usuario/IP
- [ ] Tests de seguridad

**Métricas de Éxito:**
- ✅ 100% endpoints protegidos
- ✅ Cache hit rate >40%
- ✅ Circuit breaker funcional (tested)
- ✅ Rate limit efectivo (<100 req/min por usuario)

---

### 🟢 Fase 3: Observabilidad y Optimización (Semanas 5-6)

**Objetivo:** Sistema observable y optimizado

**Features:**
1. ✅ Métricas Prometheus (ISSUE #9) - 2 días
2. ✅ Logging estructurado - 1 día
3. ✅ Tracing OpenTelemetry - 2 días
4. ✅ Grafana dashboards - 1 día
5. ✅ Alerting (PagerDuty/Slack) - 4 horas
6. ✅ Performance optimization - 2 días

**Entregables:**
- [ ] Métricas completas exportadas
- [ ] Dashboards Grafana operativos
- [ ] Tracing end-to-end
- [ ] Alerts configurados
- [ ] Performance mejorado 20-30%
- [ ] Tests >80% cobertura

**Métricas de Éxito:**
- ✅ Latencia p95 < 2s (reducción 33%)
- ✅ Throughput >500 req/s
- ✅ MTTR (Mean Time To Recovery) < 5 min
- ✅ Cobertura tests >80%

---

### 🚀 Fase 4: Escalabilidad (Semanas 7-8)

**Objetivo:** Sistema escalable horizontalmente

**Features:**
1. ✅ Kubernetes manifests - 3 días
2. ✅ Horizontal Pod Autoscaling - 1 día
3. ✅ Load balancer config - 4 horas
4. ✅ CDN para static files - 3 horas
5. ✅ Database connection pooling optimizado - 4 horas
6. ✅ Async workers para background tasks - 2 días

**Entregables:**
- [ ] Deploy en Kubernetes cluster
- [ ] Auto-scaling configurado
- [ ] Load balancer operativo
- [ ] CDN para assets
- [ ] Message queue (Celery + Redis)
- [ ] Documentación deployment

**Métricas de Éxito:**
- ✅ Scale de 1 → 10 pods sin downtime
- ✅ Latencia estable bajo carga
- ✅ Auto-scale responde en <30s
- ✅ 99.9% uptime

---

### 💎 Fase 5: Features Avanzadas (Semanas 9-12)

**Objetivo:** Diferenciación y features innovadoras

**Features:**
1. ✅ Multi-idioma (i18n) - 2 días
2. ✅ Voice input/output - 3 días
3. ✅ Exportar historial (PDF) - 2 días
4. ✅ Integración EHR (Electronic Health Records) - 1 semana
5. ✅ Analítica avanzada - 3 días
6. ✅ Mobile app (React Native) - 3 semanas

**Entregables:**
- [ ] Soporte español, inglés, portugués
- [ ] Transcripción voz a texto
- [ ] Síntesis de voz (TTS)
- [ ] Exportar PDFs con logo
- [ ] API EHR integrada
- [ ] Dashboard de analítica
- [ ] App móvil iOS/Android

**Métricas de Éxito:**
- ✅ >30% usuarios usan voice
- ✅ >50% descargan PDF
- ✅ EHR sync <5s
- ✅ App rating >4.5★

---

## 📊 ESTIMACIÓN DE COSTOS

### Infraestructura (Monthly)

| Recurso | Specs | Costo Estimado |
|---------|-------|----------------|
| **Compute (Kubernetes)** | 3x nodes, 4 vCPU, 16GB RAM | $250/mes |
| **Database (PostgreSQL)** | Managed, 2 vCPU, 8GB RAM | $100/mes |
| **Redis (Cache)** | Managed, 1GB RAM | $30/mes |
| **Storage (S3/Blob)** | 100GB logs + backups | $20/mes |
| **CDN** | CloudFlare Pro | $20/mes |
| **Monitoring** | Datadog/New Relic | $100/mes |
| **Total Infraestructura** | | **~$520/mes** |

### APIs

| API | Uso Estimado | Costo |
|-----|--------------|-------|
| **OpenAI GPT-5.1** | 1M tokens/día (~30M/mes) | $600-900/mes |
| **Google Speech-to-Text** | 10k min/mes | $150/mes |
| **Total APIs** | | **~$750-1050/mes** |

### Desarrollo

| Fase | Horas | Costo (@ $75/hr) |
|------|-------|------------------|
| **Fase 1** (2 semanas) | 80h | $6,000 |
| **Fase 2** (2 semanas) | 80h | $6,000 |
| **Fase 3** (2 semanas) | 80h | $6,000 |
| **Fase 4** (2 semanas) | 80h | $6,000 |
| **Fase 5** (4 semanas) | 160h | $12,000 |
| **Total Desarrollo** | 480h | **$36,000** |

### Total Proyecto (3 meses)

```
Desarrollo:         $36,000 (one-time)
Infraestructura:    $520 × 3 =  $1,560
APIs:               $900 × 3 =  $2,700
──────────────────────────────────────
TOTAL:              $40,260
```

---

## 🎯 MÉTRICAS DE ÉXITO

### Technical KPIs

| Métrica | Actual | Target | Mejora |
|---------|--------|--------|--------|
| **Uptime** | 95% | 99.9% | +4.9% |
| **Latency (p95)** | 5s | 2s | -60% |
| **Throughput** | 100 req/s | 500 req/s | 5x |
| **Error Rate** | 5% | <0.1% | -98% |
| **Test Coverage** | 14% | 80% | +66% |
| **Cache Hit Rate** | 0% | 50% | +50% |
| **MTTR** | 30 min | 5 min | -83% |

### Business KPIs

| Métrica | Target (3 meses) |
|---------|------------------|
| **Consultas/día** | 1,000+ |
| **Usuarios activos** | 500+ |
| **Satisfacción** | >4.5/5 ★ |
| **Tiempo promedio respuesta** | <3 min |
| **Accuracy triaje** | >85% |
| **Conversiones (free → paid)** | >10% |

---

## 🔐 CONSIDERACIONES DE SEGURIDAD

### Compliance

**Regulaciones aplicables:**
- 🏥 **HIPAA** (Health Insurance Portability and Accountability Act)
- 🇪🇺 **GDPR** (General Data Protection Regulation)
- 📋 **ISO 27001** (Information Security Management)

**Requerimientos:**

1. **Encriptación**
   - [x] En tránsito (TLS 1.3)
   - [ ] En reposo (patient_info, messages)
   - [ ] Keys en KMS (AWS/Azure Key Vault)

2. **Auditoría**
   - [ ] Logs de acceso
   - [ ] Logs de modificación de datos
   - [ ] Retención 7 años (HIPAA)

3. **Acceso**
   - [ ] Autenticación fuerte (MFA)
   - [ ] Role-based access control
   - [ ] Least privilege principle

4. **Backup**
   - [ ] Backups diarios encriptados
   - [ ] Disaster recovery plan
   - [ ] RTO <4 horas, RPO <1 hora

### Penetration Testing

**Scheduled:**
- Internal testing (quarterly)
- External audit (annually)
- Bug bounty program (ongoing)

---

## 📝 CONCLUSIONES

### Estado Actual

El proyecto **LangGraph Medical Center** tiene una **arquitectura sólida** con patrones de diseño bien aplicados y una separación clara de responsabilidades. Sin embargo, enfrenta **issues críticos** que impiden su uso en producción:

1. 🔴 Incompatibilidad Flask + eventlet + asyncpg
2. 🔴 Sin autenticación/autorización
3. 🔴 Datos médicos sin encriptar
4. 🔴 Baja cobertura de tests

### Recomendación Principal

**MIGRAR A FASTAPI** es la decisión correcta porque:
- ✅ Resuelve ISSUE #1 (event loop conflicts)
- ✅ Mejora performance 3-4x
- ✅ Habilita features modernos (auto-docs, type safety)
- ✅ Inversión justificada (3 días vs beneficios a largo plazo)

### Roadmap Sugerido

**Prioridad 1** (Crítico - 2 semanas):
- Migración a FastAPI
- Encriptación de datos
- Tests básicos

**Prioridad 2** (Importante - 4 semanas):
- Autenticación/autorización
- Circuit breaker
- Cache Redis
- Observabilidad

**Prioridad 3** (Mejoras - 8 semanas):
- Escalabilidad (Kubernetes)
- Features avanzadas
- Mobile app

### ROI Esperado

**Inversión:** $40,260 (3 meses)

**Beneficios:**
- Sistema production-ready con compliance
- Capacidad 5x usuarios
- Reducción 60% costos operativos (cache)
- Reducción 83% tiempo de resolución de issues

**Break-even:** 6-9 meses (asumiendo $500/mes revenue/usuario)

---

## 📞 PRÓXIMOS PASOS

1. **Revisión de este plan** con stakeholders
2. **Aprobar presupuesto** ($40k)
3. **Crear branch** `feature/fastapi-migration`
4. **Iniciar Fase 1** (migración)
5. **Daily standups** durante implementación
6. **Deploy a staging** (semana 2)
7. **UAT** (User Acceptance Testing)
8. **Deploy a producción** (semana 3)

---

**Documento creado por:** AI Assistant
**Fecha:** 28 de diciembre de 2025
**Versión:** 1.0
**Estado:** DRAFT - Pending Review

---

## 📎 ANEXOS

### A. Comparación de Frameworks

| Feature | Flask | FastAPI |
|---------|-------|---------|
| Async support | Bolt-on (eventlet) | Native |
| Performance | ~1000 req/s | ~3000 req/s |
| Validation | Manual | Pydantic auto |
| Docs | Manual | OpenAPI auto |
| Type hints | Optional | Required |
| WebSocket | flask-socketio | Native |
| Learning curve | Easy | Moderate |
| Community | Huge | Growing fast |
| Production ready | ✅ | ✅ |

### B. Herramientas Recomendadas

**Development:**
- IDE: VSCode + Pylance
- Linting: Ruff
- Formatting: Ruff
- Type checking: Mypy
- Testing: Pytest
- Pre-commit: pre-commit hooks

**Deployment:**
- Container: Docker
- Orchestration: Kubernetes
- CI/CD: GitHub Actions
- Registry: Docker Hub / GHCR

**Monitoring:**
- Metrics: Prometheus + Grafana
- Logging: Loki / ELK
- Tracing: Jaeger / Tempo
- APM: Datadog / New Relic
- Errors: Sentry

**Security:**
- Secrets: AWS Secrets Manager / Vault
- Scanning: Trivy / Snyk
- WAF: CloudFlare
- DDoS: CloudFlare

### C. Referencias

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [OpenAI API](https://platform.openai.com/docs)
- [PostgreSQL Best Practices](https://wiki.postgresql.org/wiki/Don%27t_Do_This)
- [HIPAA Compliance Checklist](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)

---

**FIN DEL DOCUMENTO**
