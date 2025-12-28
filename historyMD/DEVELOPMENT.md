# 🛠️ Development Guide - LangGraph Medical Center

Este documento contiene las instrucciones para desarrolladores del proyecto.

## 📦 Dependency Management con `uv`

Este proyecto usa [`uv`](https://github.com/astral-sh/uv) como gestor de dependencias moderno y rápido.

### ¿Por qué uv?

- ⚡ **10-100x más rápido** que pip/poetry
- 🔒 **Lockfile con hashes** para reproducibilidad completa
- 🎯 **Resolución de dependencias determinística**
- 🚀 **Zero-config** - Funciona out-of-the-box

### Comandos Básicos

```bash
# Instalar todas las dependencias (prod + dev)
uv sync --extra dev

# Solo dependencias de producción
uv sync

# Agregar una nueva dependencia
uv add <package>

# Agregar dependencia de desarrollo
uv add --dev <package>

# Actualizar dependencias
uv lock --upgrade

# Ejecutar script con el virtualenv activado
uv run python -m pytest

# Activar virtualenv manualmente
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
uv run pytest

# Tests con cobertura
uv run pytest --cov=src --cov-report=html

# Tests específicos
uv run pytest tests/test_agents.py -v

# Tests marcados (unit, integration, e2e)
uv run pytest -m unit
uv run pytest -m integration
```

## 🔍 Code Quality

### Linting con Ruff

```bash
# Check de linting (sin modificar archivos)
uv run ruff check src/

# Auto-fix issues
uv run ruff check src/ --fix

# Check + auto-fix con unsafe fixes
uv run ruff check src/ --fix --unsafe-fixes
```

### Formatting con Ruff

```bash
# Formatear código
uv run ruff format src/

# Check formato sin modificar
uv run ruff format src/ --check
```

### Type Checking con Mypy

```bash
# Check de tipos
uv run mypy src/

# Check específico
uv run mypy src/agents/

# Modo strict
uv run mypy src/ --strict
```

## 🔐 Pre-commit Hooks

Pre-commit hooks automáticamente ejecutan checks antes de cada commit.

```bash
# Instalar hooks
uv run pre-commit install

# Ejecutar manualmente en todos los archivos
uv run pre-commit run --all-files

# Ejecutar en archivos staged
uv run pre-commit run

# Actualizar versiones de hooks
uv run pre-commit autoupdate
```

## 🐳 Docker Development

```bash
# Build de la imagen
docker build -t medical-center:latest -f docker/Dockerfile .

# Ejecutar con docker-compose
cd docker
docker-compose up --build

# Solo servicios específicos
docker-compose up postgres
docker-compose up app

# Logs
docker-compose logs -f app

# Reiniciar servicios
docker-compose restart app
```

## 🚀 Running the Application

### Modo Desarrollo

```bash
# Con Flask development server
uv run python src/web/app.py

# Con Gunicorn (producción-like)
uv run gunicorn --bind 0.0.0.0:5000 \
    --workers 1 \
    --worker-class eventlet \
    --timeout 300 \
    src.web.app:app
```

### Variables de Entorno

Crear archivo `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.1
DATABASE_URL=postgresql://medical_user:medical_password@localhost:5432/medical_db
FLASK_SECRET_KEY=your-secret-key-here
FLASK_DEBUG=True
LOG_LEVEL=INFO
```

## 📊 Database Management

```bash
# Conectar a PostgreSQL (si usas Docker)
docker-compose exec postgres psql -U medical_user -d medical_db

# Backup de DB
docker-compose exec postgres pg_dump -U medical_user medical_db > backup.sql

# Restore de DB
docker-compose exec -T postgres psql -U medical_user -d medical_db < backup.sql
```

## 🔧 Troubleshooting

### Error: "Import could not be resolved"

**Problema:** Tu IDE no encuentra las dependencias instaladas con `uv`.

**Solución:**
```bash
# Asegúrate de que tu IDE use el virtualenv de uv
# Path del virtualenv: .venv/

# VS Code: Selecciona Python Interpreter
Ctrl+Shift+P → "Python: Select Interpreter" → ./.venv/bin/python

# PyCharm: Settings → Project → Python Interpreter → Add → Existing → .venv/
```

### Error: "uv: command not found"

**Problema:** `uv` no está en el PATH.

**Solución:**
```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Agregar al PATH
export PATH="$HOME/.local/bin:$PATH"

# Hacerlo permanente (agrega a ~/.bashrc o ~/.zshrc):
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Error: "Failed to hardlink files"

**Problema:** Sistemas de archivos diferentes (común en WSL).

**Solución:**
```bash
# Usar copy mode en lugar de hardlinks
export UV_LINK_MODE=copy

# O en cada comando:
uv sync --link-mode=copy
```

## 📝 Workflow Recomendado

1. **Antes de empezar a codear:**
   ```bash
   git checkout -b feature/mi-feature
   uv sync --extra dev
   ```

2. **Durante desarrollo:**
   ```bash
   # Escribir código
   # Ejecutar tests frecuentemente
   uv run pytest tests/test_mi_feature.py
   
   # Check de calidad
   uv run ruff check src/ --fix
   uv run mypy src/
   ```

3. **Antes de commit:**
   ```bash
   # Pre-commit se ejecuta automáticamente, pero puedes forzarlo:
   uv run pre-commit run --all-files
   
   # Si todo OK:
   git add .
   git commit -m "feat: mi nueva feature"
   ```

4. **Antes de push:**
   ```bash
   # Ejecutar toda la suite de tests
   uv run pytest --cov=src
   
   # Verificar que no rompiste nada
   git push origin feature/mi-feature
   ```

## 🎯 Best Practices

### 1. Type Hints en TODO el código

```python
# ❌ MAL
def process_data(data):
    return data.upper()

# ✅ BIEN
def process_data(data: str) -> str:
    return data.upper()
```

### 2. Docstrings en funciones públicas

```python
def evaluate(message: str, session_id: UUID) -> SpecialistEvaluation:
    """
    Evalúa si un caso pertenece a esta especialidad.
    
    Args:
        message: Mensaje del paciente
        session_id: ID de la sesión
    
    Returns:
        Evaluación del especialista
    """
    ...
```

### 3. Tests para código nuevo

```python
# tests/test_mi_feature.py
import pytest

def test_mi_nueva_funcion():
    result = mi_nueva_funcion(input_data)
    assert result == expected_output
```

### 4. Logging estructurado

```python
from loguru import logger

logger.info("User message received", session_id=str(session_id), user_id=user_id)
```

## 📚 Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Preguntas?** Contacta al equipo de Medical AI.
