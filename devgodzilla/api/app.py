from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devgodzilla.api import schemas
from devgodzilla.api.routes import projects, protocols, steps, agents, clarifications, speckit
from devgodzilla.api.routes import metrics, webhooks, events

app = FastAPI(
    title="DevGodzilla API",
    description="REST API for DevGodzilla AI Development Pipeline",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(projects.router, tags=["Projects"])
app.include_router(protocols.router, tags=["Protocols"])
app.include_router(steps.router, tags=["Steps"])
app.include_router(agents.router, tags=["Agents"])
app.include_router(clarifications.router, tags=["Clarifications"])
app.include_router(speckit.router, tags=["SpecKit"])
app.include_router(metrics.router)  # /metrics
app.include_router(webhooks.router)  # /webhooks/*
app.include_router(events.router)  # /events

@app.get("/health", response_model=schemas.Health)
def health_check():
    """Health check endpoint."""
    return schemas.Health()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
