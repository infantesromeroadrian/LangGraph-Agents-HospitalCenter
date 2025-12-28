# Guía de Deployment - LangGraph Medical Center

## 🚀 Deployment con Docker

### Requisitos Previos

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2 GB RAM mínimo
- 10 GB espacio en disco

### 1. Preparación

```bash
# Clonar repositorio
git clone <repository-url>
cd langgraph-medical-center

# Crear archivo .env desde ejemplo
cp env.example .env
```

### 2. Configurar Variables de Entorno

Editar `.env` con tus credenciales:

```env
# OpenAI (REQUERIDO)
OPENAI_API_KEY=sk-proj-xxxxx

# Flask (REQUERIDO en producción)
FLASK_SECRET_KEY=genera-un-secret-key-seguro-aqui
FLASK_DEBUG=False

# PostgreSQL (ya configurado)
DATABASE_URL=postgresql://medical_user:medical_password@postgres:5432/medical_db
```

### 3. Construir y Ejecutar

```bash
cd docker
docker-compose up --build
```

### 4. Verificar Deployment

```bash
# Health check
curl http://localhost:5000/health

# Debería retornar:
# {
#   "status": "healthy",
#   "services": {
#     "database": "connected",
#     "llm": "configured",
#     "graph": "initialized"
#   }
# }
```

### 5. Acceder a la Aplicación

- **Web UI**: http://localhost:5000
- **PgAdmin** (dev): http://localhost:5050
  - Email: admin@medical.com
  - Password: admin

---

## 🔧 Deployment en Producción

### Variables de Entorno Críticas

```env
# Producción
FLASK_DEBUG=False
FLASK_SECRET_KEY=<secreto-fuerte-de-64-caracteres>

# PostgreSQL seguro
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>

# Logging
LOG_LEVEL=WARNING
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
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
    environment:
      FLASK_DEBUG: "False"
    volumes:
      - ./src:/app/src:ro  # Read-only en prod
```

### Ejecutar en Producción

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 🔒 Seguridad en Producción

### Checklist de Seguridad

- [ ] `FLASK_SECRET_KEY` cambiado y seguro (64+ caracteres)
- [ ] `FLASK_DEBUG=False` en producción
- [ ] PostgreSQL con password fuerte
- [ ] Volúmenes read-only donde sea posible
- [ ] Contenedores corriendo como non-root
- [ ] Firewall configurado (solo puertos necesarios)
- [ ] TLS/HTTPS configurado (usar reverse proxy)
- [ ] Rate limiting activo
- [ ] Logs monitoreados

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
    }
}
```

---

## 📊 Monitoreo

### Logs

```bash
# Ver logs en tiempo real
docker-compose logs -f app

# Logs de PostgreSQL
docker-compose logs -f postgres

# Logs específicos
docker-compose logs --tail=100 app
```

### Métricas

Endpoints para monitoreo:
- `/health` - Health check general
- `/metrics` - Métricas Prometheus (TODO: implementar)

### Backups de PostgreSQL

```bash
# Backup manual
docker-compose exec postgres pg_dump -U medical_user medical_db > backup_$(date +%Y%m%d).sql

# Restaurar
docker-compose exec -T postgres psql -U medical_user medical_db < backup_20251227.sql
```

---

## 🔄 Actualización del Sistema

### Zero-Downtime Deployment

1. **Build nueva imagen**:
```bash
docker-compose build app
```

2. **Crear nuevo contenedor**:
```bash
docker-compose up -d --no-deps --scale app=2 app
```

3. **Verificar health**:
```bash
curl http://localhost:5000/health
```

4. **Remover contenedor viejo**:
```bash
docker-compose up -d --no-deps --scale app=1 --remove-orphans app
```

### Rollback

```bash
# Volver a versión anterior
docker-compose down
docker-compose pull app:previous-tag
docker-compose up -d
```

---

## 🐛 Troubleshooting

### Error: Cannot connect to PostgreSQL

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps postgres

# Ver logs
docker-compose logs postgres

# Reiniciar servicio
docker-compose restart postgres
```

### Error: Port 5000 already in use

```bash
# Cambiar puerto en docker-compose.yml
services:
  app:
    ports:
      - "8000:5000"  # External:Internal
```

### Error: Out of memory

```bash
# Aumentar límites en docker-compose.yml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 4G
```

---

## 📈 Escalamiento

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
services:
  app:
    deploy:
      replicas: 3
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - app
```

### Vertical Scaling

- Aumentar CPU/memoria en `deploy.resources`
- Ajustar `DB_POOL_SIZE` según carga
- Configurar workers de Gunicorn

---

## 🔍 Mantenimiento

### Limpieza de Sesiones Antiguas

```python
# Script de maintenance
from src.services.database_service import db_service

async def cleanup():
    await db_service.cleanup_old_sessions(days=30)
```

### Rotación de Logs

Los logs rotan automáticamente:
- Máximo 10 MB por archivo
- 5 archivos de backup
- Configurado en `logging_config.py`

---

## 📞 Soporte

Para problemas de deployment:
1. Verificar logs: `docker-compose logs`
2. Health check: `curl http://localhost:5000/health`
3. Verificar variables de entorno en `.env`
4. Revisar documentación en `docs/`

---

**Versión del Documento**: 1.0  
**Última actualización**: 2025-12-27

