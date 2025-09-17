"""
Gunicorn configuration for Railway production deployment
"""
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 8080)}"
backlog = 2048

# Worker processes
workers = 2  # Limited for Railway resources
worker_class = "sync"
worker_connections = 1000
timeout = 300  # 5 minutes to handle slow scraping
keepalive = 2

# Restart workers after this many requests, with up to this much jitter
max_requests = 100
max_requests_jitter = 10

# Restart workers after this many seconds
max_worker_lifetime = 300
max_worker_lifetime_jitter = 30

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'ogscraper'

# Server mechanics
preload_app = True
sendfile = True
reuse_port = True
chdir = '/app'

# Memory management
worker_tmp_dir = '/dev/shm'

# Graceful timeout for shutdowns
graceful_timeout = 30