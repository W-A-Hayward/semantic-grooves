"""gunicorn settings for the container."""
import os

bind = "0.0.0.0:8000"

# One process on purpose: the embedding model (about 1.3 GB in memory) is loaded once and
# shared by all request threads. Scale out with more containers, not more workers.
workers = 1
threads = int(os.environ.get("SG_THREADS", "4"))

# The first request after start-up must not time out while the model warms up.
timeout = 120
accesslog = "-"
errorlog = "-"


def post_worker_init(worker):
    """Load the model when the worker starts, so the first search is not the slow one."""
    if os.environ.get("SG_PRELOAD_MODEL", "1") == "1":
        from semantic_grooves.embedding import get_model
        get_model()
