# DevGodzilla Deployment Guide

> Production deployment instructions for DevGodzilla

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (production)
- Docker & Docker Compose (optional)
- Windmill instance (for orchestration)

---

## Deployment Options

### Option 1: Docker Compose (Recommended)

```yaml
# docker-compose.yml
version: '3.8'

services:
  devgodzilla-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/devgodzilla
      - WINDMILL_BASE_URL=http://windmill:8000
    depends_on:
      - db
      - windmill

  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=devgodzilla
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=devgodzilla
    volumes:
      - pgdata:/var/lib/postgresql/data

  windmill:
    image: ghcr.io/windmill-labs/windmill:main
    ports:
      - "8001:8000"

volumes:
  pgdata:
```

```bash
docker-compose up -d
```

### Option 2: Systemd Service

```ini
# /etc/systemd/system/devgodzilla.service
[Unit]
Description=DevGodzilla API
After=network.target postgresql.service

[Service]
User=devgodzilla
WorkingDirectory=/opt/devgodzilla
Environment="DATABASE_URL=postgresql://user:pass@localhost/devgodzilla"
ExecStart=/opt/devgodzilla/.venv/bin/uvicorn devgodzilla.api.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable devgodzilla
sudo systemctl start devgodzilla
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `WINDMILL_BASE_URL` | Windmill API URL | `http://localhost:8000` |
| `WINDMILL_TOKEN` | Windmill API token | Required |
| `LOG_LEVEL` | Logging level | `INFO` |
| `API_HOST` | API bind host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |

---

## Database Setup

### 1. Create Database

```sql
CREATE DATABASE devgodzilla;
CREATE USER devgodzilla WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE devgodzilla TO devgodzilla;
```

### 2. Run Migrations

```bash
cd devgodzilla
export DATABASE_URL=postgresql://devgodzilla:password@localhost/devgodzilla
alembic upgrade head
```

---

## Reverse Proxy (nginx)

```nginx
# /etc/nginx/sites-available/devgodzilla
server {
    listen 80;
    server_name devgodzilla.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
    }
}
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

Add to Prometheus config:

```yaml
scrape_configs:
  - job_name: 'devgodzilla'
    static_configs:
      - targets: ['localhost:8000']
```

---

## Security Checklist

- [ ] Use HTTPS in production
- [ ] Set strong database password
- [ ] Configure CORS appropriately
- [ ] Enable rate limiting
- [ ] Set up log rotation
- [ ] Configure firewall rules
- [ ] Enable database backups

---

## Troubleshooting

### API not starting

```bash
# Check logs
journalctl -u devgodzilla -f

# Test database connection
python -c "from devgodzilla.db import Database; Database().test_connection()"
```

### Windmill connection issues

```bash
# Test Windmill API
curl $WINDMILL_BASE_URL/api/version
```
