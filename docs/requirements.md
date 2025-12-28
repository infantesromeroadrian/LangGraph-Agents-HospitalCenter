# Documento de Requisitos - LangGraph Medical Center

**Proyecto**: Sistema de Agentes Médicos con LangGraph  
**Fecha**: 2025-12-27  
**Estado**: Aprobado  
**Versión**: 1.0

---

## 1. CONTEXTO EMPRESARIAL

### Problema a Resolver

Los sistemas médicos actuales no aprovechan la capacidad de múltiples agentes especializados trabajando en paralelo para proporcionar mejores diagnósticos iniciales y derivaciones apropiadas.

### Objetivo Medible

- Reducir tiempo de triaje inicial en 60%
- Precisión en derivación a especialista correcto > 90%
- Conversación natural con memoria persistente 100%

### Usuarios Finales

- Pacientes que buscan orientación médica inicial
- Profesionales de salud que necesitan sistema de triaje
- Perfil técnico: cualquier usuario, interfaz conversacional simple

### Presupuesto y Timeline

- **Tipo**: MVP Production-Ready
- **Timeline**: 5 semanas de desarrollo
- **Presupuesto**: Infraestructura cloud + API OpenAI

---

## 2. DATOS

### Datos Disponibles

- **Tipo**: Texto no estructurado (consultas de pacientes)
- **Volumen**: Conversaciones en tiempo real
- **Formato**: Mensajes de chat

### Calidad de Datos

- Input del usuario: texto libre, puede contener errores ortográficos
- No requiere dataset de entrenamiento (usa LLM pre-entrenado)

### Ubicación de Datos

- PostgreSQL para persistencia de conversaciones
- Checkpoints de LangGraph en PostgreSQL
- Logs estructurados en archivos

### Consideraciones Legales

- **PII**: Potencialmente información de salud sensible
- **Compliance**: No es sistema de diagnóstico oficial, solo orientación
- **GDPR**: Datos almacenados con posibilidad de eliminación

---

## 3. SOLUCIÓN AI/ML

### Tipo de Problema

- **Tipo**: Sistema multi-agente con RAG implícito
- **Categoría**: NLP, clasificación de intención médica, generación de respuestas
- **Approach**: Orquestación paralela de agentes especializados

### Modelos Pre-entrenados

- **LLM Principal**: GPT-5.1 de OpenAI
- **Razón**: Capacidades multimodales, contexto extenso (1M+ tokens)
- **Alternativas**: GPT-4 Turbo, Claude 3.5 Sonnet

### Métricas de Éxito

| Métrica | Objetivo | Medición |
|---------|----------|----------|
| Precisión triaje | > 85% | Especialista correcto seleccionado |
| Tiempo respuesta | < 5s | Triaje + evaluación + consenso |
| Satisfacción usuario | > 4.5/5 | Encuestas post-conversación |
| Memoria funcional | 100% | Contexto mantenido en conversación |

### Interpretabilidad

- Cada agente explica su razonamiento
- Transparencia en selección de especialista
- Consenso documentado con confianza (0-100%)

### Constraintes

- **Latencia**: Respuesta completa < 5 segundos
- **Costo**: Optimizar tokens enviados a GPT-5.1
- **Escalabilidad**: Hasta 100 sesiones concurrentes

---

## 4. ARQUITECTURA Y TECNOLOGÍAS

### Lenguajes

- **Python 3.11+**: Backend, agentes, orquestación

### Frameworks y Librerías

**Core**:
- LangGraph 0.2.45 - Orquestación de agentes
- LangChain 0.3.10 - Integración LLM
- OpenAI 1.57.4 - Acceso a GPT-5.1

**Web**:
- Flask 3.1.0 - Backend web
- Flask-SocketIO 5.4.1 - WebSocket streaming
- Flask-CORS 5.0.0 - CORS handling

**Database**:
- asyncpg 0.30.0 - PostgreSQL async
- psycopg2-binary 2.9.10 - PostgreSQL sync

**Testing**:
- pytest 8.3.4
- pytest-asyncio 0.24.0
- pytest-cov 6.0.0

### Deployment

- **Contenedores**: Docker multi-stage build
- **Orquestación**: Docker Compose
- **Base de Datos**: PostgreSQL 15 en contenedor
- **Servidor**: Gunicorn + Gevent para async

### Infraestructura de Datos

- **PostgreSQL**: Sesiones, mensajes, evaluaciones, checkpoints
- **Esquema**:
  - `checkpoints` - Estado de LangGraph
  - `sessions` - Sesiones de conversación
  - `messages` - Historial chat
  - `specialist_evaluations` - Evaluaciones paralelas

### Orquestación de Pipeline

- **LangGraph StateGraph**: Orquestación estado
- **Send API**: Ejecución paralela de agentes
- **AsyncPostgresSaver**: Checkpointing automático
- **Streaming**: Eventos en tiempo real

### Integraciones

- **OpenAI API**: GPT-5.1 para LLM
- **WebSocket**: Comunicación bidireccional tiempo real
- **REST API**: Endpoints para sesiones y datos

---

## 5. SEGURIDAD Y COMPLIANCE

### Datos Sensibles

- **PII Mínima**: Conversaciones médicas
- **Tratamiento**: Datos encriptados en tránsito (TLS)
- **Almacenamiento**: PostgreSQL con autenticación

### Regulaciones

- **Disclaimer**: Sistema de orientación, no diagnóstico oficial
- **GDPR**: Derecho al olvido implementado (clear_session)
- **HIPAA-aware**: No almacena PHI identificable

### Encriptación

- **En tránsito**: HTTPS/WSS para todo el tráfico
- **En reposo**: PostgreSQL con autenticación fuerte
- **Secrets**: Variables de entorno, no hardcoded

### Consideraciones Éticas

- Sistema siempre recomienda consulta presencial
- No reemplaza diagnóstico médico profesional
- Transparencia en limitaciones del sistema
- No discriminación por demografía

---

## 6. MONITOREO Y MANTENIMIENTO

### Monitoreo en Producción

**Métricas**:
- Latencia por nodo del grafo
- Tasa de error por especialista
- Uso de tokens OpenAI
- Sesiones activas concurrentes

**Herramientas**:
- Logs estructurados con emojis
- Health check endpoint
- PostgreSQL monitoring

### Detección de Drift

- **Tipos de drift**: No aplicable (no hay modelo entrenado)
- **Monitoreo**: Calidad de respuestas LLM
- **Alertas**: Errores OpenAI, timeouts

### Estrategia de Reentrenamiento

- No requiere reentrenamiento (usa LLM pre-entrenado)
- Actualización de prompts según feedback
- Ajuste de parámetros de consenso

### Mantenimiento

- **Equipo**: Desarrolladores con conocimiento Python/LangGraph
- **Documentación**: README, código autodocumentado, diagramas
- **Ownership**: Equipo interno
- **Actualizaciones**: Prompts, configuración, nuevos especialistas

---

## 7. ARQUITECTURA PROPUESTA (ALTO NIVEL)

### Componentes Principales

1. **Triage Agent**: Análisis inicial de síntomas
2. **8 Specialist Agents**: Evaluación paralela especializada
3. **Consensus Agent**: Selección del mejor especialista
4. **LangGraph StateGraph**: Orquestación y flujo
5. **PostgreSQL**: Persistencia y checkpointing
6. **Flask + WebSocket**: Interfaz web con streaming
7. **GPT-5.1**: Motor LLM para todos los agentes

### Flujo de Datos

```
Usuario → Flask → LangGraph → [Triaje → Fan-out → 8 Especialistas → Consenso → Chat]
                      ↕                                                      ↕
                 PostgreSQL                                          GPT-5.1 API
```

---

## 8. RIESGOS Y MITIGACIONES

### Riesgo 1: Latencia Alta en Evaluaciones Paralelas

- **Impacto**: Experiencia de usuario degradada
- **Mitigación**: Timeouts agresivos, fallback a medicina general
- **Probabilidad**: Media

### Riesgo 2: Costos OpenAI Elevados

- **Impacto**: Presupuesto excedido
- **Mitigación**: Cache de evaluaciones, límites de tokens, rate limiting
- **Probabilidad**: Alta

### Riesgo 3: Respuestas Médicas Incorrectas

- **Impacto**: Crítico para reputación y seguridad
- **Mitigación**: Disclaimers claros, prompts con restricciones, siempre recomendar consulta presencial
- **Probabilidad**: Media

### Riesgo 4: Falla de PostgreSQL

- **Impacto**: Pérdida de memoria conversacional
- **Mitigación**: Backups automáticos, health checks, reinicio automático
- **Probabilidad**: Baja

---

## 9. FASES DEL PROYECTO

### Fase 1: Core Infrastructure (1 semana)

- Setup proyecto, Docker, PostgreSQL
- Servicios básicos (LLM, DB)
- Modelos de datos

### Fase 2: Agentes Médicos (1 semana)

- Clase base de agentes
- 8 especialistas implementados
- Triaje y consenso

### Fase 3: LangGraph Orchestration (1 semana)

- StateGraph configurado
- Nodos y edges definidos
- Ejecución paralela con Send API
- Checkpointing PostgreSQL

### Fase 4: Web Interface (1 semana)

- Flask backend con API REST
- WebSocket para streaming
- Frontend con chat y visualización D3.js

### Fase 5: Testing y Docs (1 semana)

- Tests unitarios, integración, E2E
- Documentación completa
- Optimización y deployment

---

## 10. CRITERIOS DE ACEPTACIÓN

- ✅ 8 especialistas médicos funcionando en paralelo
- ✅ Triaje identifica síntomas y recomienda especialidades
- ✅ Consenso selecciona especialista con justificación
- ✅ Conversación fluida con memoria persistente
- ✅ Visualización del grafo en tiempo real
- ✅ Streaming de respuestas vía WebSocket
- ✅ Tests con cobertura > 80%
- ✅ Logs estructurados y monitoring básico
- ✅ Docker Compose para deployment
- ✅ README con instrucciones completas

---

**Estado del Documento**: ✅ APROBADO  
**Aprobado por**: Medical AI Team  
**Fecha de Aprobación**: 2025-12-27

