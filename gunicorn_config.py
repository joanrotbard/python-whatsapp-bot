"""Gunicorn configuration for production."""
import multiprocessing
import os

# Server socket
# Use PORT environment variable if available (for Railway, Heroku, etc.), otherwise default to 8000
port = os.getenv("PORT", "8000")
bind = f"0.0.0.0:{port}"
backlog = 2048

# Worker processes
# Use environment variable if set, otherwise use a reasonable default
# For Railway/cloud: 2-4 workers is usually enough since heavy processing is in Celery
# For local/server: can use more workers based on CPU count
workers_env = os.getenv("GUNICORN_WORKERS")
if workers_env:
    workers = int(workers_env)
else:
    # Default: 2-4 workers for cloud platforms, more for dedicated servers
    cpu_count = multiprocessing.cpu_count()
    if cpu_count <= 2:
        workers = 2  # Minimum 2 workers
    elif cpu_count <= 4:
        workers = 4  # Good for most cloud platforms
    else:
        workers = min(cpu_count, 8)  # Cap at 8 for dedicated servers

worker_class = "sync"
worker_connections = 1000
timeout = 120  # Increased for Railway - some requests may take longer
keepalive = 5
graceful_timeout = 30  # Time to wait for workers to finish before killing them

# Logging
# Send all logs to stdout so Railway doesn't mark them as errors
accesslog = "-"  # stdout
errorlog = "-"  # stdout (changed from stderr so Railway doesn't mark as errors)
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Enable capture output to see all logs
capture_output = True
enable_stdio_inheritance = True

# Redirect stderr to stdout to prevent Railway from marking logs as errors
import sys
sys.stderr = sys.stdout

# Process naming
proc_name = "whatsapp-bot"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

