from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sqlalchemy.exc import OperationalError

from bioforge import __version__
from bioforge.core.config import Settings, get_settings
from bioforge.core.database import create_engine, create_session_factory
from bioforge.core.exceptions import BioForgeError, NotFoundError, ValidationError
from bioforge.core.storage import ObjectStorage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    app.state.session_factory = create_session_factory(engine)
    app.state.settings = settings
    app.state.storage = ObjectStorage(
        endpoint=settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
    )
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="BioForge",
        description="AI-first bioinformatics platform",
        version=__version__,
        lifespan=lifespan,
    )

    # Exception handlers
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(BioForgeError)
    async def bioforge_error_handler(request: Request, exc: BioForgeError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(OperationalError)
    async def db_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable. Start PostgreSQL with: docker compose up -d"},
        )

    # Routers
    from bioforge.api.routers import (
        agents,
        modules,
        pipelines,
        projects,
        results,
        search,
        sequences,
        workspaces,
    )

    app.include_router(workspaces.router, prefix="/api/v1/workspaces", tags=["workspaces"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(sequences.router, prefix="/api/v1/sequences", tags=["sequences"])
    app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
    app.include_router(results.router, prefix="/api/v1/results", tags=["results"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["search"])

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    return app
