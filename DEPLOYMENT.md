# DevGodzilla Deployment Guide

## Prerequisites
- Docker & Docker Compose
- 8GB+ RAM recommended (for compiling Windmill)

## Architecture
The system runs as a set of Docker containers:
1.  **`devgodzilla-api`**: The core API service (FastAPI).
2.  **`windmill`**: The extended Windmill platform (with DevGodzilla frontend).
3.  **`db`**: PostgreSQL (stores data for both).
4.  **`redis`**: Redis (for job queues/caching).

## Setup & Run

1.  **Initialize Database Config**:
    Ensure `scripts/init-db.sh` is executable:
    ```bash
    chmod +x scripts/init-db.sh
    ```

2.  **Build and Run**:
    Use the custom DevGodzilla compose file:
    ```bash
    docker compose -f docker-compose.devgodzilla.yml up --build -d
    ```

    > **Note**: The first build takes a while (15-20 mins) as it compiles Windmill dependencies (Rust) from scratch.

3.  **Access Services**:
    - **DevGodzilla API**: `http://localhost:8000/docs`
    - **Windmill UI**: `http://localhost:8080`

## Development

- The `devgodzilla-api` container mounts the local directory, so code changes execute immediately (hot reload).
- Frontend changes to Windmill require a rebuild:
  ```bash
  docker compose -f docker-compose.devgodzilla.yml build windmill
  ```
