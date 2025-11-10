# 🔧 Troubleshooting Guide

## Problema: No recibo respuestas en WhatsApp

### Paso 1: Verificar Logs

Cuando envías un mensaje, deberías ver en los logs:

```
Incoming webhook: Message event
Processing message synchronously for 971559098067
Starting message processing...
Received message from 971559098067 (Name): Hello...
Sending typing indicator...
Generating OpenAI response...
OpenAI response generated: ...
Sending response to WhatsApp...
✓ Response sent successfully to 971559098067
```

### Paso 2: Verificar que el Webhook Recibe el Mensaje

```bash
# En los logs deberías ver:
"Incoming webhook: Message event"
```

Si no ves esto, el problema es que WhatsApp no está enviando el webhook o hay un problema de red.

### Paso 3: Verificar Servicios

Ejecuta el script de prueba:
```bash
python test_webhook.py
```

Esto verificará:
- ✅ App se crea correctamente
- ✅ Service container funciona
- ✅ Message handler se crea
- ✅ Procesamiento funciona

### Paso 4: Verificar Errores Comunes

#### Error: "Service container not available"
**Solución**: Verifica que `_initialize_services` se ejecuta en `app/__init__.py`

#### Error: "Redis connection failed"
**Solución**: 
- Redis es opcional ahora, la app debería funcionar sin él
- Si quieres Redis: `docker run -d -p 6379:6379 redis:7-alpine`

#### Error: "OpenAI API error"
**Solución**: 
- Verifica `OPENAI_API_KEY` en `.env`
- Verifica `OPENAI_ASSISTANT_ID` en `.env`

#### Error: "WhatsApp API error"
**Solución**:
- Verifica `ACCESS_TOKEN` en `.env` (puede haber expirado)
- Verifica `PHONE_NUMBER_ID` en `.env`

### Paso 5: Verificar Variables de Entorno

```bash
# Verifica que estas variables estén en .env:
ACCESS_TOKEN=...
PHONE_NUMBER_ID=...
OPENAI_API_KEY=...
OPENAI_ASSISTANT_ID=...
```

### Paso 6: Probar Endpoint de Envío Manual

```bash
curl -X POST http://localhost:8000/api/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "971559098067",
    "message": "Test message"
  }'
```

Si esto funciona, el problema es en el webhook. Si no funciona, el problema es en los servicios.

### Paso 7: Verificar Logs Detallados

Habilita debug mode en `.env`:
```env
DEBUG=true
```

Esto mostrará logs más detallados de cada paso.

## Checklist de Diagnóstico

- [ ] ¿Ves "Incoming webhook: Message event" en los logs?
- [ ] ¿Ves "Processing message synchronously" en los logs?
- [ ] ¿Ves "Starting message processing" en los logs?
- [ ] ¿Ves "Received message from..." en los logs?
- [ ] ¿Ves "Generating OpenAI response" en los logs?
- [ ] ¿Ves "Response sent successfully" en los logs?
- [ ] ¿Hay algún error en los logs?

## Comandos Útiles

```bash
# Ver logs en tiempo real
tail -f logs/app.log  # si usas archivo de logs

# Probar webhook localmente
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=..." \
  -d @sample_webhook.json

# Verificar Redis
redis-cli ping

# Verificar Celery (si lo usas)
celery -A app.infrastructure.celery_app:celery_app inspect active
```

