# ✅ Actualización de Variables de Entorno

## 🔄 Cambio de Nombres

Hemos renombrado las variables de `FLASK_*` a `APP_*` para reflejar que ahora usamos **FastAPI**.

### Variables Renombradas:

| Antes (Flask) | Después (FastAPI) |
|---------------|-------------------|
| `FLASK_HOST` | `APP_HOST` |
| `FLASK_PORT` | `APP_PORT` |
| `FLASK_DEBUG` | `APP_DEBUG` |
| `FLASK_SECRET_KEY` | `APP_SECRET_KEY` |

---

## 📝 Actualizar tu archivo `.env`

### Opción 1: Editar Manualmente

Abre tu `.env` y cambia:

```bash
# ANTES:
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
FLASK_SECRET_KEY=tu-secret-aqui

# DESPUÉS:
APP_HOST=0.0.0.0
APP_PORT=5000
APP_DEBUG=False
APP_SECRET_KEY=tu-secret-aqui
```

### Opción 2: Usar sed (Linux/Mac)

```bash
cd /mnt/c/Users/infan/OneDrive/Desktop/AIR/Projects/AI-Projects/LangGraph-Medical-Center

sed -i 's/FLASK_HOST/APP_HOST/g' .env
sed -i 's/FLASK_PORT/APP_PORT/g' .env
sed -i 's/FLASK_DEBUG/APP_DEBUG/g' .env
sed -i 's/FLASK_SECRET_KEY/APP_SECRET_KEY/g' .env
```

### Opción 3: Recrear desde .env.example

```bash
# Backup del .env actual
cp .env .env.backup

# Copiar el nuevo template
cp .env.example .env

# Editar y agregar:
# - Tu OPENAI_API_KEY
# - Generar APP_SECRET_KEY con: python -c "import secrets; print(secrets.token_hex(32))"
```

---

## ✅ Validar que funciona

Después de actualizar el `.env`:

```bash
# Levantar Docker
cd docker
docker-compose up --build

# Verificar que inicia sin errores
# Deberías ver: "Server: FastAPI on 0.0.0.0:5000"
```

---

## 🎯 Tu `.env` debe quedar así:

```bash
# OpenAI
OPENAI_API_KEY=sk-tu-key-aqui
OPENAI_MODEL=gpt-5.1

# Database
DATABASE_URL=postgresql://medical_user:medical_password@localhost:5432/medical_db

# Application (FastAPI) ← NUEVOS NOMBRES
APP_HOST=0.0.0.0
APP_PORT=5000
APP_DEBUG=False
APP_SECRET_KEY=genera-uno-con-secrets

# LangGraph
RECURSION_LIMIT=50

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:5000,http://127.0.0.1:5000
```

