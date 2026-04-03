# BioForge

AI-first bioinformatics platform for designing and executing bioinformatics pipelines.

## Architecture

- **Backend**: FastAPI + Pydantic v2 + async SQLAlchemy + PostgreSQL
- **AI**: Claude Agent SDK + MCP tool servers
- **Bio**: Biopython, pydna, primer3-py for DNA assembly
- **Frontend**: Streamlit (MVP)
- **Package layout**: `src/bioforge/` with hatchling build

## Commands

```bash
# Dev server
uvicorn bioforge.api.app:create_app --factory --reload

# Tests
pytest

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# DB migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Docker services
docker compose up -d
```

## Key Patterns

- **Module system**: All bioinformatics tools implement `BioForgeModule` ABC in `src/bioforge/modules/base.py`
- **Repositories**: Generic `BaseRepository[T]` for async CRUD in `src/bioforge/repositories/base.py`
- **Constraints**: Assembly constraints implement `BaseConstraint` with `check(partition) -> ConstraintResult`
- **MCP tools**: Decorated with `@tool` from claude_agent_sdk or fastmcp
- **Pipeline DSL**: `PipelineBuilder` fluent API in `src/bioforge/pipeline_engine/dsl.py`

## Conventions

- Async everywhere (asyncpg, aioboto3, async handlers)
- Pydantic v2 for all request/response validation
- Polars for vectorized bioinformatics computation
- structlog for structured logging
- All thresholds centralized in config classes
