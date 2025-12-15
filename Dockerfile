FROM node:20-alpine AS console-builder

WORKDIR /console

COPY web/console/package.json web/console/package-lock.json ./
RUN npm ci

COPY web/console/ ./
RUN npm run build || echo "Build failed, using existing dist if available"


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app


# Install devgodzilla dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN pip install uvicorn fastapi

COPY . /app

EXPOSE 8000

# Default command runs devgodzilla API
CMD ["uvicorn", "devgodzilla.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
