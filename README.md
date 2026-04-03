<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

```
 ____  _       _____                    
| __ )(_) ___ |  ___|__  _ __ __ _  ___ 
|  _ \| |/ _ \| |_ / _ \| '__/ _` |/ _ \
| |_) | | (_) |  _| (_) | | | (_| |  __/
|____/|_|\___/|_|  \___/|_|  \__, |\___|
                              |___/      
```

# BioForge

**The bioinformatics platform that actually gets out of your way.**

BioForge is an AI-native workspace for designing, executing, and iterating on bioinformatics pipelines. Drop in a DNA sequence, get back an optimized Gibson Assembly design with thermodynamically validated overhangs. Build multi-step pipelines with a fluent Python DSL. Let an AI agent reason about your biology and invoke tools on your behalf.

No more duct-taping CLI tools together with bash scripts at 2am.

---

## What Can It Do?

### DNA Assembly Designer

The flagship module. Hand it a sequence up to **1,000,000 bp** and it will:

- Partition it into fragments within **[2000, 2500] bp** for Gibson Assembly
- Design orthogonal sticky-end overhangs at each junction
- Enforce **5 constraint classes** simultaneously:
  - Fragment length bounds
  - Overhang quality (Tm, GC content, homopolymer avoidance)
  - Pairwise orthogonality (Hamming distance + nearest-neighbor ΔΔG)
  - Secondary structure avoidance (hairpin ΔG)
- Run a **simulated annealing optimizer** with multi-restart search
- Validate the assembly via **pydna** simulation

```python
from bioforge.modules.assembly.core.solver import AssemblySolver

solver = AssemblySolver(seed=42)
result = solver.solve("ATCGATCG..." * 1000)  # Your sequence here

print(f"Fragments: {result.partition.num_fragments}")
print(f"Feasible: {result.feasible}")
print(f"Time: {result.total_time_s:.2f}s")
print(f"Quality: {result.quality_scores['total']:.2f}")
```

### Pipeline Engine

Build DAGs of bioinformatics steps with a fluent Python API. The engine handles dependency resolution, parallel scheduling, and can export to **Nextflow DSL2** for production cloud execution.

```python
from bioforge.pipeline_engine.dsl import PipelineBuilder

pipeline = (
    PipelineBuilder("gibson_assembly", "Full assembly design pipeline")
    .add_step("assembly.design", "design",
              params={"min_fragment_bp": 2000, "max_fragment_bp": 2500})
    .build()
)
```

### AI Agent

An AI agent with access to all platform tools via MCP (Model Context Protocol). Describe what you want in plain English, and it designs the assembly, checks the constraints, and explains the results.

```bash
curl -X POST http://localhost:8000/api/v1/agents/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Design a Gibson Assembly for this 50kb plasmid with no cuts in the GFP cassette",
    "workspace_id": "...",
    "project_id": "..."
  }'
```

### REST API

32 endpoints across workspaces, projects, sequences, pipelines, results, agents, and modules. Full OpenAPI docs at `/docs`.

### Streamlit Dashboard

Interactive UI for assembly design, sequence exploration, and pipeline monitoring. No frontend expertise required.

---

## Architecture

```
                    ┌──────────────────────┐
                    │   Streamlit UI       │
                    │   :8501              │
                    └─────────┬────────────┘
                              │
                    ┌─────────▼────────────┐
                    │   FastAPI Backend    │
                    │   :8000             │
                    │   32 endpoints      │
                    ├─────────────────────┤
                    │   Service Layer     │
                    ├─────────────────────┤
                    │   Repository Layer  │
                    │   (async SQLAlchemy)│
                    ├─────────────────────┤
                    │   PostgreSQL + S3   │
                    └──┬──────────────┬───┘
                       │              │
              ┌────────▼───┐   ┌──────▼────────┐
              │ AI Agent   │   │ Pipeline      │
              │ MCP Tools  │   │ DAG Executor  │
              │ Tool Hooks │   │ Nextflow      │
              └────────┬───┘   └──────┬────────┘
                       │              │
              ┌────────▼──────────────▼────────┐
              │     Module System              │
              │  ┌───────────┐ ┌────────────┐  │
              │  │ Assembly  │ │  (yours    │  │
              │  │ Module    │ │   here)    │  │
              │  └───────────┘ └────────────┘  │
              └────────────────────────────────┘
```

**Everything is a module.** The assembly engine is just the first one. Want to add BLAST, alignment, or variant calling? Implement `BioForgeModule`, register it via entry points, and the platform automatically:
- Exposes it as REST API capabilities
- Makes it available as pipeline steps
- Registers MCP tools for the AI agent
- Adds it to the module registry

---

## The Science Under the Hood

### Thermodynamic Engine

Overhangs are evaluated using the **SantaLucia (1998) unified nearest-neighbor model** — the same thermodynamic framework used by Primer3 and every serious oligo design tool. We wrap `primer3-py` for production accuracy (±2°C Tm) with a pure-Python fallback for environments where the C library isn't available.

### Constraint System

Five constraints, evaluated in order with early termination:

| # | Constraint | What It Checks | Algorithm |
|---|-----------|---------------|-----------|
| C1 | Fragment Length | Each fragment ∈ [2000, 2500] bp | O(k) bounds check |
| C2 | Overhang Quality | Tm ∈ [50, 65]°C, GC ∈ [40%, 60%], no homopolymers ≥ 5 | O(k) per-overhang |
| C3 | Orthogonality | Pairwise Hamming ≥ 5, ΔΔG ≥ 4 kcal/mol | Numpy-vectorized O(k²·L) |
| C4 | Hairpin | No strong secondary structures (ΔG > -2 kcal/mol) | O(k) primer3 calls |
| C5 | Composite | Weighted combination, C3 at 5× weight | Early termination |

### Optimizer

**Simulated annealing** with boundary perturbation. Each iteration picks the worst constraint violation, tries shifting the responsible boundary by {±5, ±10, ±25, ±50} bp or adjusting the overhang length by ±2 bp. Accepts improvements greedily and worse solutions with decreasing probability (cooling schedule over 500 iterations). Up to 50 random restarts.

For a **1M bp sequence** (~444 fragments), the solver targets **< 5 minutes** with incremental evaluation reducing the per-iteration cost from O(k²) to O(k).

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL + MinIO)

### Install

```bash
git clone https://github.com/allaspectsdev/BioForge.git
cd BioForge

# Start infrastructure
docker compose up -d

# Install the package
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys if you want the AI agent
```

### Run

```bash
# API server (http://localhost:8000)
uvicorn bioforge.api.app:create_app --factory --reload

# Streamlit UI (http://localhost:8501)
streamlit run src/bioforge/ui/app.py

# Run tests
pytest -v
```

### Try It

```python
# Quick assembly design
from bioforge.modules.assembly.core.solver import AssemblySolver

# Generate a random sequence (or use your own)
import random
seq = ''.join(random.choices('ATCG', k=10000))

solver = AssemblySolver(seed=42)
result = solver.solve(seq)

for frag in result.fragments:
    print(f"  Fragment {frag['index']}: {frag['start']}-{frag['end']} ({frag['length']} bp)")

for oh in result.overhangs:
    print(f"  Overhang {oh['index']}: {oh['sequence']} (Tm={oh['tm']}°C, GC={oh['gc']:.0%})")

print(f"\nQuality: {result.quality_scores['total']:.2f}")
print(f"Feasible: {result.feasible}")
```

---

## Project Structure

```
src/bioforge/
├── core/               # Config, database, storage, exceptions
├── models/             # SQLAlchemy ORM (10 tables)
├── schemas/            # Pydantic v2 request/response models
├── repositories/       # Generic CRUD + entity-specific queries
├── services/           # Business logic layer
├── api/                # FastAPI app + 7 routers (32 endpoints)
├── agent/              # AI agent client, prompts, hooks, sessions
├── mcp/                # MCP server (4 tools)
├── pipeline_engine/    # DSL, DAG graph, executor, Nextflow bridge
├── modules/
│   ├── base.py         # BioForgeModule ABC
│   ├── registry.py     # Plugin discovery & management
│   └── assembly/       # Flagship module
│       ├── core/       # Solver, constraints, thermo, optimizer
│       ├── tools.py    # MCP tool definitions
│       └── tests/      # 8 tests (all passing)
└── ui/                 # Streamlit dashboard (5 pages)
```

## Writing a Module

Every bioinformatics capability is a plugin:

```python
from bioforge.modules.base import BioForgeModule, ModuleInfo, ModuleCapability

class MyAlignmentModule(BioForgeModule):
    def info(self):
        return ModuleInfo(name="alignment", version="0.1.0",
                         description="Sequence alignment", author="You")

    def capabilities(self):
        return [ModuleCapability(
            name="align_sequences",
            description="Align two DNA sequences",
            input_schema={...},
            output_schema={...},
            handler=self._align,
        )]

    def pipeline_steps(self):
        return [...]  # Register as pipeline step types

    async def _align(self, request):
        # Your implementation here
        ...
```

Register in `pyproject.toml`:

```toml
[project.entry-points."bioforge.modules"]
alignment = "your_package:MyAlignmentModule"
```

Done. The platform picks it up automatically at startup.

---

## API Endpoints

| Group | Method | Path | Description |
|-------|--------|------|-------------|
| Health | GET | `/health` | Platform status |
| Workspaces | CRUD | `/api/v1/workspaces` | Workspace management |
| Projects | CRUD | `/api/v1/projects` | Project management |
| Sequences | CRUD + Import | `/api/v1/sequences` | FASTA/GenBank import, sequence CRUD |
| Pipelines | CRUD + Run | `/api/v1/pipelines` | Pipeline define, execute, monitor |
| Results | GET | `/api/v1/results` | Result retrieval |
| Agents | POST | `/api/v1/agents/query` | AI agent natural language queries |
| Modules | GET | `/api/v1/modules` | Module discovery |

Full interactive docs at `http://localhost:8000/docs` when running.

---

## Tech Stack

| What | Why |
|------|-----|
| **FastAPI** | Async, auto-generated OpenAPI docs, type-safe |
| **Pydantic v2** | Runtime validation, serialization, settings management |
| **SQLAlchemy 2.0** | Async ORM with asyncpg for PostgreSQL |
| **Polars** | Vectorized computation (10x faster than pandas) |
| **NumPy** | Pairwise Hamming distance matrix (vectorized broadcast) |
| **primer3-py** | SantaLucia nearest-neighbor thermodynamics |
| **pydna** | Gibson Assembly simulation |
| **Biopython** | FASTA/GenBank parsing, sequence manipulation |
| **FastMCP** | Model Context Protocol server for AI tool integration |
| **Streamlit** | Interactive dashboard with zero frontend code |
| **Docker** | Reproducible deployment |

---

## Roadmap

- [ ] Sequence alignment module (BLAST, minimap2)
- [ ] Variant calling module (BCFtools integration)
- [ ] Visual pipeline DAG editor in the UI
- [ ] Golden Gate Assembly support (Type IIS restriction enzymes)
- [ ] Batch assembly design for multi-construct projects
- [ ] Cloud execution backend (AWS Batch, Google Cloud Life Sciences)
- [ ] User authentication and workspace sharing
- [ ] WebSocket-based real-time pipeline monitoring

---

## Contributing

PRs welcome. The architecture is designed to be extended:

1. **New bioinformatics tool?** Write a `BioForgeModule`.
2. **Better optimizer?** Swap the strategy in `solver.py`.
3. **New constraint?** Implement `BaseConstraint`, add to `CompositeConstraint`.
4. **Frontend feature?** Add a Streamlit page.

```bash
# Development setup
pip install -e ".[dev]"
pytest -v              # Run tests
ruff check src/        # Lint
ruff format src/       # Format
```

---

## License

MIT License. Use it, fork it, ship it.

---

<p align="center">
  <i>Built for biologists who code and coders who biology.</i>
</p>
