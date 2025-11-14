#!/bin/bash

# Script para detener todos los componentes
# Uso: ./stop.sh

echo "🛑 Deteniendo WhatsApp Bot..."

# Detener Celery worker
if [ -f celery.pid ]; then
    echo "Deteniendo Celery worker..."
    kill $(cat celery.pid) 2>/dev/null || true
    rm celery.pid
    echo "✓ Celery worker detenido"
fi

# Also kill any remaining celery processes
pkill -f "celery.*worker" 2>/dev/null || true

# Detener procesos de gunicorn
echo "Deteniendo Flask application..."
pkill -f "gunicorn.*app:create_app" || true
pkill -f "python.*run.py" || true
echo "✓ Flask application detenida"

echo "✅ Todos los procesos detenidos"

