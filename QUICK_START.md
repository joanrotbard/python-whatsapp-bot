# 🚀 Guía Rápida de Inicio

## 📋 Requisitos Previos

### 1. **Python 3.13+**
```bash
python --version
# Debe mostrar Python 3.13 o superior
```

### 2. **Redis** (Requerido)
Redis es necesario para:
- Almacenamiento de threads
- Sistema de colas (Celery)
- Rate limiting

**Opción A: Docker (Recomendado)**
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

**Opción B: Instalación Local**
```bash
# macOS
brew install redis
brew services start redis

# Linux (Ubuntu/Debian)
sudo apt-get install redis-server
sudo systemctl start redis

# Verificar que Redis está corriendo
redis-cli ping
# Debe responder: PONG
```

### 3. **Variables de Entorno**
Copia `example.env` a `.env` y completa los valores:
```bash
cp example.env .env
```

## 📦 Instalación

### 1. **Instalar Dependencias**

**Con uv (Recomendado):**
```bash
uv sync
```

**O con pip:**
```bash
pip install -r requirements-production.txt
```

### 2. **Configurar Variables de Entorno**

Edita `.env` y completa estos valores **obligatorios**:

```env
# WhatsApp API (OBLIGATORIO)
ACCESS_TOKEN="tu_access_token"
PHONE_NUMBER_ID="tu_phone_number_id"
VERIFY_TOKEN="tu_verify_token"

# OpenAI (OBLIGATORIO)
OPENAI_API_KEY="tu_openai_api_key"
OPENAI_ASSISTANT_ID="tu_assistant_id"

# Redis (Ya configurado por defecto si usas Docker)
REDIS_URL="redis://localhost:6379/0"
```

**Variables opcionales** (tienen valores por defecto):
- `REDIS_THREAD_TTL=3600` (1 hora)
- `CELERY_BROKER_URL=redis://localhost:6379/1`
- `RATELIMIT_ENABLED=true`
- `ENABLE_METRICS=true`

## 🏃 Ejecutar la Aplicación

La aplicación necesita **3 procesos** corriendo simultáneamente:

### 1. **Redis** (Si no está corriendo)
```bash
# Con Docker
docker start redis

# O verificar que está corriendo
redis-cli ping
```

### 2. **Celery Worker** (Procesa mensajes en background)
```bash
celery -A app.infrastructure.celery_app:celery_app worker --loglevel=info
```

**O con más workers para mejor performance:**
```bash
celery -A app.infrastructure.celery_app:celery_app worker --loglevel=info --concurrency=4
```

### 3. **Flask Application** (Servidor web)
```bash
# Desarrollo
python run.py

# Producción (Recomendado)
gunicorn -c gunicorn_config.py "app:create_app()"
```

## ✅ Verificar que Todo Funciona

### 1. **Health Check**
```bash
curl http://localhost:8000/health
# Debe responder: {"status": "healthy", "service": "whatsapp-bot"}
```

### 2. **Readiness Check** (Verifica Redis)
```bash
curl http://localhost:8000/health/ready
# Debe responder: {"status": "ready", "checks": {"redis": true, "overall": true}}
```

### 3. **Métricas** (Si está habilitado)
```bash
curl http://localhost:8000/metrics
# Debe mostrar métricas de Prometheus
```

### 4. **Verificar Celery Worker**
En otra terminal:
```bash
celery -A app.infrastructure.celery_app:celery_app inspect active
# Debe mostrar workers activos
```

## 🔧 Solución de Problemas

### Error: "Redis connection failed"
```bash
# Verificar que Redis está corriendo
redis-cli ping

# Si no responde, iniciar Redis
docker start redis
# o
redis-server
```

### Error: "Module not found"
```bash
# Reinstalar dependencias
uv sync
# o
pip install -r requirements-production.txt
```

### Error: "Celery worker not processing tasks"
1. Verificar que el worker está corriendo
2. Verificar que Redis está accesible
3. Verificar `CELERY_BROKER_URL` en `.env`

### Error: "Missing required environment variables"
Completa todos los valores obligatorios en `.env`:
- `ACCESS_TOKEN`
- `PHONE_NUMBER_ID`
- `OPENAI_API_KEY`
- `OPENAI_ASSISTANT_ID`

## 📊 Monitoreo

### Ver Logs de Celery
```bash
celery -A app.infrastructure.celery_app:celery_app events
```

### Ver Tareas en Cola
```bash
celery -A app.infrastructure.celery_app:celery_app inspect reserved
```

### Ver Estadísticas de Workers
```bash
celery -A app.infrastructure.celery_app:celery_app inspect stats
```

## 🎯 Resumen de Comandos

```bash
# Terminal 1: Redis (si no usa Docker)
redis-server

# Terminal 2: Celery Worker
celery -A app.infrastructure.celery_app:celery_app worker --loglevel=info

# Terminal 3: Flask App
gunicorn -c gunicorn_config.py "app:create_app()"
```

## 📝 Checklist de Inicio

- [ ] Python 3.13+ instalado
- [ ] Redis instalado y corriendo
- [ ] Dependencias instaladas (`uv sync` o `pip install`)
- [ ] Archivo `.env` configurado con valores obligatorios
- [ ] Redis accesible (`redis-cli ping` responde PONG)
- [ ] Celery worker corriendo
- [ ] Flask app corriendo
- [ ] Health check responde correctamente (`/health`)

## 🚀 Producción

Para producción, considera:

1. **Usar Gunicorn** en lugar de `run.py`
2. **Configurar Nginx** como reverse proxy
3. **Usar Supervisor** o **systemd** para gestionar procesos
4. **Configurar Sentry** para error tracking
5. **Habilitar métricas** de Prometheus
6. **Usar Redis Cluster** para alta disponibilidad
7. **Múltiples workers** de Celery

Ver `SCALABILITY_ANALYSIS.md` para más detalles.

