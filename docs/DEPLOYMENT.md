# Guia de Deployment - LangGraph Medical Center

## Deployment con Docker

### Requisitos Previos

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2 GB RAM minimo
- 10 GB espacio en disco

### 1. Preparacion

```bash
git clone <repository-url>
cd langgraph-medical-center

cp .env.example .env
```

### 2. Configurar Variables de Entorno

Editar `.env` con valores reales. **No usar los valores por defecto en produccion.**

Variables criticas a configurar:

| Variable | Descripcion |
|---|---|
| `OPENAI_API_KEY` | API key del proveedor LLM |
| `APP_SECRET_KEY` | Secreto de 64+ caracteres para tokens |
| `JWT_SECRET_KEY` | Secreto independiente para JWT |
| `ADMIN_API_KEY` | Clave admin de 32+ caracteres |
| `DATABASE_URL` | Connection string de PostgreSQL |
| `AUTH_COOKIE_SECURE` | `True` en HTTPS, `False` en local |

> Los valores que empiezan con `change-this` o `replace` son placeholders.
> La aplicacion rechazara iniciar si detecta placeholders en las claves de seguridad.

Generar secretos seguros:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Construir y Ejecutar

```bash
cd docker
docker compose up --build -d
```

### 4. Verificar Deployment

```bash
curl http://localhost:5000/health

# 200 OK = todos los servicios operativos
# 503 = DB o grafo no disponibles
```

### 5. Acceder a la Aplicacion

- **Web UI**: http://localhost:5000
- **PgAdmin** (solo dev): `docker compose --profile dev up pgadmin`

> La documentacion API (Swagger/ReDoc) solo esta disponible con `APP_DEBUG=True`.

---

## Deployment en Produccion

### Checklist de Seguridad

- [ ] Secretos generados con `secrets.token_urlsafe(48)` (no placeholders)
- [ ] `APP_DEBUG=False`
- [ ] `AUTH_COOKIE_SECURE=True`
- [ ] PostgreSQL con password fuerte
- [ ] Puerto 5432 de PostgreSQL NO expuesto al exterior
- [ ] TLS/HTTPS configurado via reverse proxy
- [ ] Rate limiting activo (defaults: 120/min read, 30/min write)
- [ ] CORS_ORIGINS restringido a dominios reales
- [ ] Logs monitoreados

### docker-compose.prod.yml

Crear un override para produccion:

```yaml
services:
  app:
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

  postgres:
    ports: []  # No exponer puerto de DB
```

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Configurar HTTPS con Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name medical.example.com;

    ssl_certificate /etc/ssl/certs/medical.crt;
    ssl_certificate_key /etc/ssl/private/medical.key;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Monitoreo

### Health Check

- **200**: todos los servicios operativos
- **503**: DB o grafo no disponibles

### Logs

```bash
docker compose logs -f app
docker compose logs --tail=100 app
```

### Metricas

- `/health` - Estado del sistema
- `/metrics` - Metricas Prometheus (requiere header `X-Admin-Key`)

### Backups de PostgreSQL

```bash
# Backup — usar credenciales de .env
docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%Y%m%d).sql

# Restaurar
docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql
```

---

## Actualizacion

1. Build nueva imagen: `docker compose build app`
2. Recrear contenedor: `docker compose up -d --no-deps app`
3. Verificar: `curl http://localhost:5000/health`

### Rollback

```bash
docker compose down
docker compose up -d --force-recreate
```

---

## Troubleshooting

| Problema | Solucion |
|---|---|
| Cannot connect to PostgreSQL | `docker compose logs postgres` y verificar que esta healthy |
| "APP_SECRET_KEY contiene un valor placeholder" | Generar secreto real con `secrets.token_urlsafe(48)` |
| Port 5000 already in use | Cambiar puerto externo en docker-compose.yml: `"8000:5000"` |
| Health devuelve 503 | DB o grafo no inicializados, revisar logs |

---

## Mantenimiento

### Limpieza de Sesiones

```python
from src.services.database_service import db_service
await db_service.cleanup_old_sessions(days=30)
```

### Rotacion de Logs

Automatica: 10 MB por archivo, 5 archivos de backup (ver `logging_config.py`).

---

**Version**: 2.0 (FastAPI) | **Actualizado**: 2026-04-10
