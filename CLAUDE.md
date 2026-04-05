# BioForge v0.3.0

AI-first bioinformatics platform with 7 modules, 22 capabilities, 22 MCP tools, and a multi-turn AI agent.

## Architecture

- **Backend**: FastAPI + Pydantic v2 + async SQLAlchemy + PostgreSQL (pgvector)
- **AI**: Anthropic API (Claude Sonnet 4.6) with multi-turn sessions, domain router, agent memory, SSE streaming
- **Bio**: Biopython, primer3-py, Evo 2 embeddings (1B/7B/20B/40B), Boltz-2 structure prediction
- **Modules**: Assembly (Gibson + Golden Gate + Codon Opt), Evo2, Structure, Alignment, Variants, Experiments, SBOL
- **Frontend**: Streamlit (with working AI Agent chat UI)
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
- **MCP tools**: 22 `@mcp.tool()` decorated functions in `src/bioforge/mcp/server.py` covering all 7 modules
- **Pipeline DSL**: `PipelineBuilder` fluent API in `src/bioforge/pipeline_engine/dsl.py`
- **Pipeline steps**: 10 registered types across assembly (3), alignment (2), evo2 (2), structure (1), variants (1), sbol (1)
- **Agent**: Multi-turn sessions with RouterAgent for domain classification and AgentMemory for cross-session knowledge
- **Structure prediction**: Boltz-2 (recommended, MIT), OpenFold3 (Apache 2.0), ESMFold (deprecated - API dead)

## Conventions

- Async everywhere (asyncpg, aioboto3, async handlers)
- Pydantic v2 for all request/response validation
- numpy for vectorized bioinformatics computation (Hamming distance matrices)
- All thresholds centralized in config dataclasses
- Optional heavy dependencies (evo2, boltz, openfold) guarded with try/except
- `datetime.now(UTC)` instead of deprecated `datetime.utcnow()`
- SBOL3 XML parsing uses ElementTree with regex fallback
