
import multiprocessing
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
threads = 2
timeout = 60
keepalive = 2
bind = "0.0.0.0:8080"
accesslog = "-"
errorlog = "-"
