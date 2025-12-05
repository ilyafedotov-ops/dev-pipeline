from prometheus_client import Counter, Histogram, generate_latest

requests_total = Counter("requests_total", "Total HTTP requests")
jobs_processed_total = Counter("jobs_processed_total", "Total jobs processed", ["job_type", "status"])
webhooks_total = Counter("webhooks_total", "Total webhooks received", ["provider", "status"])
request_latency_ms = Histogram(
    "requests_duration_seconds",
    "Request duration seconds",
    ["path", "method", "status"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10),
)


class Metrics:
    def inc_request(self) -> None:
        requests_total.inc()

    def inc_job(self, job_type: str, status: str) -> None:
        jobs_processed_total.labels(job_type=job_type, status=status).inc()

    def inc_webhook(self, provider: str) -> None:
        webhooks_total.labels(provider=provider, status="received").inc()

    def inc_webhook_status(self, provider: str, status: str) -> None:
        webhooks_total.labels(provider=provider, status=status).inc()

    def observe_request(self, path: str, method: str, status: str, duration_s: float) -> None:
        request_latency_ms.labels(path=path, method=method, status=status).observe(duration_s)

    def to_prometheus(self) -> bytes:
        return generate_latest()


metrics = Metrics()
