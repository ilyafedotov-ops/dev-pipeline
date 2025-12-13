FROM node:20-alpine AS console-builder

WORKDIR /console

COPY web/console/package.json web/console/package-lock.json ./
RUN npm ci

COPY web/console/ ./
RUN npm run build


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements-orchestrator.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Publish the built Vite console so the API can serve it at /console.
COPY --from=console-builder /console/dist /app/tasksgodzilla/api/frontend_dist

EXPOSE 8010

CMD ["bash", "-c", "python scripts/api_server.py --host 0.0.0.0 --port 8010"]
