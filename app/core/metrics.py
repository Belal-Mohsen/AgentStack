from prometheus_client import Counter, Histogram, Gauge
from starlette_prometheus import metrics, PrometheusMiddleware
# Telemetry Context
# ==================================================
# Prometheus Metrics Definition
# ==================================================

# 1. Standard HTTP Metrics
# Counts total requests by method (GET/POST) and status code (200, 400, 500)
http_requests_total = Counter(
    "http_requests_total", 
    "Total number of HTTP requests", 
    ["method", "endpoint", "status"]
)

# Tracks latency distribution (p50, p95, p99)
# This helps us identify slow endpoints.
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", 
    "HTTP request duration in seconds", 
    ["method", "endpoint"]
)

# 2. Infrastructure Metrics
# Helps us detect connection leaks in SQLAlchemy
db_connections = Gauge(
    "db_connections", 
    "Number of active database connections"
)

# 3. AI / Business Logic Metrics
# Critical for tracking LLM performance and cost. 
# We use custom buckets because LLM calls are much slower than DB calls.
llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "Time spent processing LLM inference",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0] 
)
llm_stream_duration_seconds = Histogram(
    "llm_stream_duration_seconds",
    "Time spent processing LLM stream inference",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 60.0]
)


orders_processed = Counter("orders_processed_total", "Total number of orders processed")
def setup_metrics(app):
    """
    Configures the Prometheus middleware and exposes the /metrics endpoint.
    """
    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics)