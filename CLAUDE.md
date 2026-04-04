# BioForge v0.2.0

AI-first bioinformatics platform with 7 modules, 22 capabilities, and a multi-turn AI agent.

## Architecture

- **Backend**: FastAPI + Pydantic v2 + async SQLAlchemy + PostgreSQL (pgvector)
- **AI**: Anthropic API with multi-turn sessions, domain router, agent memory
- **Bio**: Biopython, primer3-py, Evo 2 embeddings, OpenFold3 structure prediction
- **Modules**: Assembly (Gibson + Golden Gate), Evo2, Structure, Alignment, Variants, Experiments, SBOL
- **Frontend**: Streamlit (MVP)
- **Package layout**: `src/bioforge/` with hatchling build

## Commands

```bash
# Dev server
uvicorn bioforge.api.app:create_app --factory --reload

# Streamlit UI
streamlit run src/bioforge/ui/app.py

# MCP server
python -m bioforge.mcp.server

# Tests
pytest

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Docker services (PostgreSQL + Redis + MinIO)
docker compose up -d
```

## Key Patterns

- **Module system**: All bioinformatics tools implement `BioForgeModule` ABC in `src/bioforge/modules/base.py`
- **7 modules**: assembly, evo2, structure, alignment, variants, experiments, sbol — registered via pyproject.toml entry points
- **Repositories**: Generic `BaseRepository[T]` for async CRUD in `src/bioforge/repositories/base.py`
- **Constraints**: Assembly constraints implement `BaseConstraint` with `check(partition) -> ConstraintResult`
- **MCP tools**: `@mcp.tool()` decorated functions in `src/bioforge/mcp/server.py` (12 tools)
- **Pipeline DSL**: `PipelineBuilder` fluent API in `src/bioforge/pipeline_engine/dsl.py`
- **Agent**: Multi-turn sessions with RouterAgent for domain classification and AgentMemory for cross-session knowledge

## Conventions

- Async everywhere (asyncpg, aioboto3, async handlers)
- Pydantic v2 for all request/response validation
- numpy for vectorized bioinformatics computation (Hamming distance matrices)
- All thresholds centralized in config dataclasses
- Optional heavy dependencies (evo2, openfold) guarded with try/except
