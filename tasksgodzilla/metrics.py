from prometheus_client import Counter, Histogram, generate_latest

requests_total = Counter("requests_total", "Total HTTP requests")
jobs_processed_total = Counter("jobs_processed_total", "Total jobs processed", ["job_type", "status"])
webhooks_total = Counter("webhooks_total", "Total webhooks received", ["provider", "status"])
job_duration_seconds = Histogram(
    "jobs_duration_seconds",
    "Job duration seconds",
    ["job_type", "status"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
)
request_latency_ms = Histogram(
    "requests_duration_seconds",
    "Request duration seconds",
    ["path", "method", "status"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10),
)
token_usage_estimated_total = Counter(
    "codex_token_estimated_total",
    "Estimated Codex tokens sent (prompt-side) grouped by phase/model",
    ["phase", "model"],
)
qa_verdict_total = Counter(
    "qa_verdict_total",
    "QA verdicts observed",
    ["verdict"],
)


class Metrics:
    def inc_request(self) -> None:
        requests_total.inc()

    def inc_job(self, job_type: str, status: str) -> None:
        jobs_processed_total.labels(job_type=job_type, status=status).inc()

    def observe_job_duration(self, job_type: str, status: str, duration_s: float) -> None:
        job_duration_seconds.labels(job_type=job_type, status=status).observe(duration_s)

    def inc_webhook(self, provider: str) -> None:
        webhooks_total.labels(provider=provider, status="received").inc()

    def inc_webhook_status(self, provider: str, status: str) -> None:
        webhooks_total.labels(provider=provider, status=status).inc()

    def observe_request(self, path: str, method: str, status: str, duration_s: float) -> None:
        request_latency_ms.labels(path=path, method=method, status=status).observe(duration_s)

    def observe_tokens(self, phase: str, model: str, tokens: int) -> None:
        token_usage_estimated_total.labels(phase=phase, model=model).inc(tokens)

    def inc_qa_verdict(self, verdict: str) -> None:
        qa_verdict_total.labels(verdict=verdict.lower()).inc()

    def to_prometheus(self) -> bytes:
        return generate_latest()


metrics = Metrics()
