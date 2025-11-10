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

# Health check (use PORT env var if available, otherwise 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, requests; port = os.getenv('PORT', '8000'); requests.get(f'http://localhost:{port}/health', timeout=5)" || exit 1

# Run with Gunicorn
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:create_app()"]

