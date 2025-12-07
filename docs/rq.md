# RQ Worker Setup (Durable Queue)

1. Set `TASKSGODZILLA_REDIS_URL` (e.g., `redis://localhost:6380/0` when using compose; 6379 if running Redis directly). Use `make compose-deps` to start the Redis/Postgres containers if you want durable queues without running the API in Docker.
2. Run API server (it will not start an in-process worker when Redis is set):
   ```bash
   .venv/bin/python scripts/api_server.py
   ```
3. Start an RQ worker in a separate process:
   ```bash
   .venv/bin/python scripts/rq_worker.py
   ```
4. Jobs enqueued via API actions/webhooks will be processed by the RQ worker using `tasksgodzilla.worker_runtime.rq_job_handler`.

Observability
-------------
- API endpoints:
  - `GET /queues` shows per-queue counts (queued/started/finished/failed) and identifies the backend (Redis/RQ; fakeredis is reported as Redis).
  - `GET /queues/jobs` lists jobs with payload, timestamps (enqueued/started/ended when available), and result/exception info for `queued/started/finished/failed`.
- RQ CLI:
  ```bash
  rq info --url "$TASKSGODZILLA_REDIS_URL"
  rq worker --url "$TASKSGODZILLA_REDIS_URL" # for ad-hoc inspection
  ```
- RQ dashboard (optional):
  ```bash
  pip install rq-dashboard
  rq-dashboard --redis-url "$TASKSGODZILLA_REDIS_URL" --port 9181
  ```
  Then browse http://localhost:9181/ to view live queues/jobs.

Env used by RQ worker:
- `TASKSGODZILLA_DB_PATH`
- `TASKSGODZILLA_REDIS_URL`
- `TASKSGODZILLA_LOG_LEVEL`

Note: Queue listing/claim APIs are not exposed yet; monitor Redis/RQ via `rq info` or the RQ dashboard.
