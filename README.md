# 🏥 LangGraph Medical Center

Sistema de agentes médicos especializados con orquestación paralela usando LangGraph, Groq (Llama/OpenAI-compatible) y PostgreSQL.

## 🎯 Características Principales

- **Orquestación Paralela**: 8 agentes especialistas evalúan casos simultáneamente
- **Memoria Persistente**: PostgreSQL para conversaciones y checkpointing de LangGraph
- **Streaming en Tiempo Real**: WebSocket para respuestas en tiempo real
- **Visualización de Grafo**: Muestra el flujo de agentes en D3.js
- **LLM LLM (Groq-compatible)**: Modelo de última generación para interacciones médicas
- **Arquitectura Modular**: Código limpio, separado por responsabilidades

## 🏗️ Arquitectura del Sistema

```
Usuario → Triaje → [8 Especialistas en Paralelo] → Consenso → Especialista Seleccionado
                                                                      ↓
                                                              Chat Conversacional
```

### Especialistas Médicos

1. **Medicina General** - Atención primaria y síntomas generales
2. **Cardiología** - Problemas cardiovasculares
3. **Neurología** - Sistema nervioso y cerebral
4. **Pediatría** - Salud infantil y adolescentes
5. **Dermatología** - Piel, cabello y uñas
6. **Traumatología** - Huesos, articulaciones y lesiones
7. **Psiquiatría** - Salud mental
8. **Oncología** - Detección y seguimiento de cáncer

## 📋 Requisitos Previos

- Docker & Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Groq API Key (or OpenAI-compatible endpoint)

## 🚀 Instalación y Ejecución

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd langgraph-medical-center
```

### 2. Configurar variables de entorno

Copiar `env.example` a `.env` y configurar:

```bash
cp env.example .env
```

Editar `.env` con tus credenciales:

```env
OPENAI_API_KEY=tu_api_key_aqui
OPENAI_BASE_URL=https://api.groq.com/openai/v1  # or https://api.openai.com/v1
OPENAI_MODEL=llama-3.3-70b-versatile             # or gpt-4o, etc.
APP_SECRET_KEY=tu_secret_key_segura
```

### 3. Ejecutar con Docker Compose

```bash
cd docker
docker-compose up --build
```

### 4. Acceder a la aplicación

- **Web UI**: http://localhost:5000
- **Health Check**: http://localhost:5000/health
- **PgAdmin** (dev): http://localhost:5050

## 🧪 Testing

Ejecutar todos los tests:

```bash
pytest tests/ -v --cov=src
```

Tests específicos:

```bash
# Tests unitarios
pytest tests/test_agents.py -v

# Tests del grafo
pytest tests/test_graph.py -v

# Tests de memoria
pytest tests/test_memory.py -v
```

## 📁 Estructura del Proyecto

```
langgraph-medical-center/
├── src/                          # Código fuente
│   ├── agents/                   # Agentes médicos
│   │   ├── base_agent.py        # Clase base abstracta
│   │   ├── triage_agent.py      # Agente de triaje
│   │   ├── consensus_agent.py   # Agente de consenso
│   │   ├── agent_factory.py     # Factory de agentes
│   │   └── specialists/         # 8 especialistas
│   ├── graph/                    # LangGraph orchestration
│   │   ├── state.py             # Estado del grafo
│   │   ├── nodes.py             # Funciones de nodos
│   │   └── medical_graph.py     # Construcción del grafo
│   ├── memory/                   # Sistema de memoria
│   │   └── conversation_memory.py
│   ├── models/                   # Modelos de datos
│   │   ├── message.py
│   │   ├── evaluation.py
│   │   └── session.py
│   ├── services/                 # Servicios
│   │   ├── llm_service.py       # Servicio LLM (OpenAI/Groq)
│   │   └── database_service.py  # Servicio PostgreSQL
│   ├── web/                      # Interfaz Flask
│   │   ├── app.py               # Aplicación principal
│   │   ├── templates/           # Templates HTML
│   │   └── static/              # CSS & JavaScript
│   ├── config/                   # Configuración
│   │   ├── settings.py          # Settings con Pydantic
│   │   └── prompts.py           # Prompts de agentes
│   └── utils/                    # Utilidades
│       ├── logging_config.py
│       └── validators.py
├── tests/                        # Tests con pytest
├── docker/                       # Docker files
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── init-db.sql
├── docs/                         # Documentación
└── requirements.txt              # Dependencias Python
```

## 🔧 Configuración Avanzada

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | API Key (Groq/OpenAI-compatible) | *requerido* |
| `OPENAI_MODEL` | Modelo LLM | `gpt-4o` |
| `DATABASE_URL` | URL de PostgreSQL | Ver env.example |
| `FLASK_PORT` | Puerto de Flask | `5000` |
| `FLASK_DEBUG` | Modo debug | `False` |
| `RECURSION_LIMIT` | Límite del grafo | `50` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

### Base de Datos

El sistema crea automáticamente las siguientes tablas:

- `checkpoints` - Estado de LangGraph
- `checkpoint_writes` - Escrituras pendientes
- `sessions` - Sesiones de conversación
- `messages` - Historial de mensajes
- `specialist_evaluations` - Evaluaciones de especialistas

## 📖 Uso del Sistema

### Flujo de Conversación

1. **Usuario inicia consulta**: "Tengo dolor en el pecho"
2. **Triaje analiza**: Identifica síntomas y urgencia
3. **Evaluación Paralela**: 8 especialistas evalúan en paralelo
4. **Consenso decide**: Selecciona el mejor especialista
5. **Chat especializado**: Conversación con el especialista asignado
6. **Memoria persistente**: Todo se guarda en PostgreSQL

### API Endpoints

#### REST API

- `POST /api/sessions` - Crear nueva sesión
- `GET /api/sessions/<id>` - Obtener información de sesión
- `GET /api/sessions/<id>/messages` - Obtener mensajes
- `GET /health` - Health check

#### WebSocket Events

- `connect` - Conexión establecida
- `join_session` - Unirse a una sesión
- `send_message` - Enviar mensaje al sistema
- `agent_response` - Respuesta de un agente
- `graph_update` - Actualización del grafo
- `thinking` - Agente procesando

## 🔐 Seguridad

- ✅ Contenedores non-root
- ✅ Secrets en variables de entorno
- ✅ Validación de inputs
- ✅ CORS configurado
- ✅ Rate limiting
- ✅ Logging estructurado sin datos sensibles

## 🛠️ Desarrollo

### Setup Local

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar tests
pytest tests/ -v
```

### Linting y Formateo

```bash
# Black
black src/ tests/

# Ruff
ruff check src/ tests/

# Type checking
mypy src/
```

## 📊 Métricas de Rendimiento

- **Tiempo de triaje**: < 2 segundos
- **Evaluación paralela (8 especialistas)**: < 3 segundos
- **Respuesta de chat**: < 2 segundos
- **Persistencia PostgreSQL**: < 100ms
- **WebSocket latency**: < 50ms

## 🐛 Troubleshooting

### Error: "Database connection failed"

```bash
# Verificar que PostgreSQL esté corriendo
docker-compose ps

# Reiniciar servicios
docker-compose restart postgres
```

### Error: "OpenAI API Key invalid"

Verificar que `OPENAI_API_KEY` en `.env` sea válida y que `OPENAI_BASE_URL` apunte al endpoint correcto (Groq, OpenAI, etc.).

### Error: "Port 5000 already in use"

```bash
# Cambiar puerto en .env
FLASK_PORT=8000

# O detener el proceso usando el puerto
lsof -ti:5000 | xargs kill -9  # macOS/Linux
```

## 📚 Recursos

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/)
- [Groq API Reference](https://console.groq.com/docs/api-reference)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## 🤝 Contribuir

1. Fork el repositorio
2. Crear feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 📝 Licencia

MIT License. Ver [LICENSE](LICENSE) para más detalles.

## 👥 Autores

- [Adrian Infantes](https://github.com/infantesromeroadrian)

## 🙏 Agradecimientos

- LangGraph por el framework de orquestación
- Groq por la API LLM compatible con OpenAI
- Comunidad open source

---

**Versión**: 1.0.0
**Estado**: Production Ready
**Última actualización**: 2025-12-27
