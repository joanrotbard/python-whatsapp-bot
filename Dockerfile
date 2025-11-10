# Multi-stage build for production
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock requirements-production.txt ./
RUN pip install uv && uv pip install --system -r requirements-production.txt

# Production stage
FROM python:3.13-slim

WORKDIR /app

# Copy only runtime dependencies
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Railway will use PORT env var if set)
EXPOSE 8000

# Health check - use curl if available, otherwise python
# Railway will handle health checks externally, but this helps Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD sh -c 'port=${PORT:-8000} && python -c "import socket; s=socket.socket(); s.settimeout(2); result=s.connect_ex((\"127.0.0.1\", int(port))); s.close(); exit(0 if result == 0 else 1)"' || exit 1

# Run with Gunicorn
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:create_app()"]

