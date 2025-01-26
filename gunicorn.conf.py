# Gunicorn configuration file
import multiprocessing
from api.utils.logger import setup_logger  # Import your custom logger setup

max_requests = 1000
max_requests_jitter = 50

bind = "0.0.0.0:8000"

worker_class = "uvicorn.workers.UvicornWorker"
workers = multiprocessing.cpu_count()

# Log configuration
accesslog = "-"  # Log all access logs to stdout
errorlog = "-"   # Log all errors to stdout
loglevel = "info"  # Set the log level to info (or debug for more verbosity)

def post_fork(server, worker):
    # This hook is called after a worker has been forked
    # Set up your custom logger here
    logger = setup_logger(debug_console=True)
    logger.info("Worker process started")
