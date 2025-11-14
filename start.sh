#!/bin/bash

# Script para iniciar todos los componentes de la aplicación
# Uso: ./start.sh

set -e

echo "🚀 Iniciando WhatsApp Bot..."

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar que Redis está corriendo
echo -e "${YELLOW}Verificando Redis...${NC}"
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis está corriendo${NC}"
else
    echo -e "${RED}✗ Redis no está corriendo${NC}"
    echo "Iniciando Redis con Docker..."
    docker run -d -p 6379:6379 --name redis redis:7-alpine || docker start redis
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis iniciado${NC}"
    else
        echo -e "${RED}✗ No se pudo iniciar Redis. Por favor inicia Redis manualmente.${NC}"
        exit 1
    fi
fi

# Verificar que .env existe
if [ ! -f .env ]; then
    echo -e "${YELLOW}Archivo .env no encontrado. Copiando desde example.env...${NC}"
    cp example.env .env
    echo -e "${YELLOW}Por favor completa los valores en .env antes de continuar${NC}"
    exit 1
fi

# Verificar variables obligatorias
echo -e "${YELLOW}Verificando variables de entorno...${NC}"
source .env

REQUIRED_VARS=("ACCESS_TOKEN" "PHONE_NUMBER_ID" "OPENAI_API_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${RED}✗ Variables faltantes en .env:${NC}"
    printf '%s\n' "${MISSING_VARS[@]}"
    exit 1
fi

echo -e "${GREEN}✓ Variables de entorno configuradas${NC}"

# Iniciar Celery worker en background
echo -e "${YELLOW}Iniciando Celery worker...${NC}"
# Use unique node name to avoid DuplicateNodenameWarning
NODE_NAME="worker@$(hostname)-$(date +%s)"
celery -A app.infrastructure.celery_app:celery_app worker --loglevel=info --detach --logfile=celery.log --pidfile=celery.pid -n "$NODE_NAME"
echo -e "${GREEN}✓ Celery worker iniciado (PID: $(cat celery.pid), Node: $NODE_NAME)${NC}"

# Iniciar Flask app
echo -e "${YELLOW}Iniciando Flask application...${NC}"
echo -e "${GREEN}✓ Aplicación iniciada en http://localhost:8000${NC}"
echo -e "${GREEN}✓ Health check: http://localhost:8000/health${NC}"
echo -e "${GREEN}✓ Métricas: http://localhost:8000/metrics${NC}"
echo ""
echo -e "${YELLOW}Presiona Ctrl+C para detener${NC}"

# Usar gunicorn en producción, run.py en desarrollo
if [ "${FLASK_ENV:-development}" = "production" ]; then
    gunicorn -c gunicorn_config.py "app:create_app()"
else
    python run.py
fi

