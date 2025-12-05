# RQ Worker Setup (Durable Queue)

1. Set `DEKSDENFLOW_REDIS_URL` (e.g., `redis://localhost:6379/0`).
2. Run API server (it will not start an in-process worker when Redis is set):
   ```bash
   .venv/bin/python scripts/api_server.py
   ```
3. Start an RQ worker in a separate process:
   ```bash
   .venv/bin/python scripts/rq_worker.py
   ```
4. Jobs enqueued via API actions/webhooks will be processed by the RQ worker using `deksdenflow.worker_runtime.rq_job_handler`.

Observability
-------------
- API endpoints:
  - `GET /queues` shows per-queue counts (queued/started/finished/failed) and identifies the backend (in-memory vs Redis/RQ).
  - `GET /queues/jobs` lists jobs with payload, timestamps (enqueued/started/ended when available), and result/exception info for `queued/started/finished/failed`.
- RQ CLI:
  ```bash
  rq info --url "$DEKSDENFLOW_REDIS_URL"
  rq worker --url "$DEKSDENFLOW_REDIS_URL" # for ad-hoc inspection
  ```
- RQ dashboard (optional):
  ```bash
  pip install rq-dashboard
  rq-dashboard --redis-url "$DEKSDENFLOW_REDIS_URL" --port 9181
  ```
  Then browse http://localhost:9181/ to view live queues/jobs.

Env used by RQ worker:
- `DEKSDENFLOW_DB_PATH`
- `DEKSDENFLOW_REDIS_URL`
- `DEKSDENFLOW_LOG_LEVEL`

Note: Queue listing/claim APIs are not exposed yet; monitor Redis/RQ via `rq info` or the RQ dashboard.
