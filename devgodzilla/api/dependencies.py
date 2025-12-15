from typing import Generator, Optional
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from devgodzilla.cli.main import get_db as cli_get_db, get_service_context as cli_get_service_context
from devgodzilla.services.base import ServiceContext

from devgodzilla.db.database import Database

def get_db():
    """Get database instance."""
    db = cli_get_db()
    try:
        yield db
    finally:
        pass

def get_service_context(
    db: Session = Depends(get_db),
    x_project_id: Optional[int] = Header(None, alias="X-Project-ID")
) -> ServiceContext:
    """Get service context."""
    # Reuse the logic from CLI for now, but in a real API we might want 
    # request-scoped logging and context
    return cli_get_service_context(project_id=x_project_id)
