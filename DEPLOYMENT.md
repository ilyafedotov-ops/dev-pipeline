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
5.  **`windmill_import`**: One-shot bootstrap job that imports scripts/flows/apps into Windmill.

## Setup & Run

1.  **Initialize Database Config**:
    Ensure `scripts/init-db.sh` is executable:
    ```bash
    chmod +x scripts/init-db.sh
    ```

2.  **Build and Run**:
    Use the default compose stack:
    ```bash
    docker compose up --build -d
    ```

    > **Note**: The first build takes a while as it compiles Windmill from source (Rust + `deno_core`/V8 for JavaScript `input_transforms`).

    If you want a faster `python`-only Windmill build (no JS `input_transforms`), set:
    ```bash
    export WINDMILL_FEATURES="static_frontend python"
    docker compose up --build -d
    ```

3.  **Import Windmill assets (auto)**:
    The stack includes `windmill_import`, which imports:
    - scripts from `windmill/scripts/devgodzilla/` → `u/devgodzilla/*`
    - flows from `windmill/flows/devgodzilla/` → `f/devgodzilla/*`
    - apps from `windmill/apps/devgodzilla/`

    Verify it ran:
    ```bash
    docker compose logs windmill_import
    ```

    Windmill token/workspace are read from `windmill/apps/devgodzilla-react-app/.env.development` by default.

3.  **Access Services**:
    - **DevGodzilla API (via nginx)**: `http://localhost:8080/docs` (or `$DEVGODZILLA_NGINX_PORT`)
    - **Windmill UI (via nginx)**: `http://localhost:8080` (or `$DEVGODZILLA_NGINX_PORT`)
    - **Readiness**: `http://localhost:8080/health/ready`

## Validating a real onboarding workflow (GitHub repo → SpecKit files)

In Windmill UI (`http://localhost:8080`), run flow `f/devgodzilla/onboard_to_tasks` with:
- `git_url`: `https://github.com/octocat/Hello-World`
- `project_name`: any unique name
- `branch`: `master` (or `main`)
- `feature_request`: a short feature request (used to generate spec/plan/tasks)

On success, generated files appear under `projects/<project_id>/<repo>/specs/<spec_id>/`.

## Development

- The `devgodzilla-api` container mounts the local directory, so code changes execute immediately (hot reload).
- Frontend changes to Windmill require a rebuild:
  ```bash
  docker compose build windmill
  ```

## Environment Variables (Compose)

- `DEVGODZILLA_DB_URL`: Postgres URL for DevGodzilla (Compose sets to `postgresql://devgodzilla:changeme@db:5432/devgodzilla_db`)
- `DEVGODZILLA_WINDMILL_URL`: Windmill base URL for DevGodzilla-to-Windmill API calls (Compose sets to `http://windmill:8000`)
- `DEVGODZILLA_WINDMILL_WORKSPACE`: Windmill workspace (Compose defaults to `demo1`)
- `DEVGODZILLA_WINDMILL_ENV_FILE`: Optional path to an env file containing `DEVGODZILLA_WINDMILL_TOKEN`/`WINDMILL_TOKEN`/`VITE_TOKEN`
