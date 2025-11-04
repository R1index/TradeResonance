import os

bind = "0.0.0.0:8080"

# Low, safe defaults for small containers; override via env if needed
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("WEB_THREADS", "2"))
worker_class = os.getenv("WORKER_CLASS", "gthread")
preload_app = False

# Stability
timeout = int(os.getenv("WEB_TIMEOUT", "60"))
keepalive = 2
max_requests = int(os.getenv("MAX_REQUESTS", "500"))
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", "50"))

accesslog = "-"
errorlog = "-"
