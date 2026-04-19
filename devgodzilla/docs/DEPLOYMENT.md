# DevGodzilla Deployment Guide

This repository ships a single Docker Compose stack (nginx + DevGodzilla API + Windmill + workers + PostgreSQL + Redis).

## Docker Compose (Recommended)

From the repo root:

```bash
docker compose up --build -d
```

Windmill assets (scripts/flows/apps) are imported by the one-shot `windmill_import` service:

```bash
docker compose logs -f windmill_import
```

### URLs (default)

- Nginx reverse proxy: `http://localhost:8080/`
- DevGodzilla OpenAPI: `http://localhost:8080/docs`
- Readiness/liveness: `http://localhost:8080/health/ready`, `http://localhost:8080/health/live`

## Systemd (Non-Docker)

```ini
# /etc/systemd/system/devgodzilla.service
[Unit]
Description=DevGodzilla API
After=network.target postgresql.service

[Service]
User=devgodzilla
WorkingDirectory=/opt/devgodzilla
Environment="DEVGODZILLA_DB_URL=postgresql://user:pass@localhost:5432/devgodzilla"
ExecStart=/opt/devgodzilla/.venv/bin/uvicorn devgodzilla.api.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Environment Variables

Set exactly one database backend. Do not set both `DEVGODZILLA_DB_URL` and `DEVGODZILLA_DB_PATH`.

| Variable | Description | Default |
|----------|-------------|---------|
| `DEVGODZILLA_DB_URL` | PostgreSQL connection string | None |
| `DEVGODZILLA_DB_PATH` | SQLite DB path (dev) | None |
| `DEVGODZILLA_LOG_LEVEL` | Logging level | `INFO` |
| `DEVGODZILLA_API_HOST` | API bind host | `0.0.0.0` |
| `DEVGODZILLA_API_PORT` | API port | `8000` |
| `DEVGODZILLA_WINDMILL_URL` | Windmill base URL (no `/api` suffix) | `http://localhost:8000` |
| `DEVGODZILLA_WINDMILL_WORKSPACE` | Windmill workspace | `devgodzilla` |
| `DEVGODZILLA_WINDMILL_TOKEN` | Windmill token (do not commit) | None |
| `DEVGODZILLA_WINDMILL_ENV_FILE` | Optional env file to source token/workspace/url | Auto-detected |

## Troubleshooting

### Health checks

```bash
curl http://localhost:8080/health
curl http://localhost:8080/health/ready
curl http://localhost:8080/health/live
```

### Windmill API

```bash
curl "${DEVGODZILLA_WINDMILL_URL:-http://localhost:8000}/api/version"
```
