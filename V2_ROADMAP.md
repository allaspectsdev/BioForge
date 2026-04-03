# BioForge V2: From Assembly Calculator to Bioinformatics Intelligence Platform

## Context

V1 proved the concept: a constraint-based Gibson Assembly solver with SantaLucia 1998 thermodynamics, wrapped in a plugin module system with an AI agent and pipeline engine. But honestly — V1 is a Gibson Assembly calculator wearing a platform costume. One module, a single-turn agent, stub UI pages, and zero foundation model integration.

V2 transforms BioForge into a platform a bioinformatician would actually use in the lab. The intern's assembly optimization concept becomes the nucleus of something much bigger — and every new capability validates the architecture they inspired.

---

## Architecture: V1 vs V2

```
V1 (what exists)                    V2 (what we're building)
─────────────────                   ──────────────────────────
1 module (assembly)            →    6 modules (assembly, evo2, structure,
                                              alignment, variants, experiments)
4 MCP tools (hardcoded)        →    25+ MCP tools (auto-registered from modules)
Single-turn agent              →    Multi-turn agent with memory, sub-agents,
                                    streaming, and tool chains
1 pipeline step type           →    15+ step types with real workflow templates
Streamlit stubs                →    React/Next.js with plasmid maps, constraint
                                    heatmaps, 3D structure viewer, chat UI
No foundation models           →    Evo 2 embeddings, variant scoring,
                                    OpenFold3 structure prediction
No wet-lab features            →    Primer ordering, synthesis feasibility,
                                    experiment tracking, SBOL import/export
15 tests                       →    200+ tests, >80% coverage
```

---

## Phase 0: Foundation Hardening (Weeks 1-2)

### 0.1 Test Infrastructure
- `tests/conftest.py` — shared fixtures: async SQLite in-memory DB, mock MinIO, pre-loaded registry
- Full CRUD tests for all 7 API routers (workspaces, projects, sequences, pipelines, results, agents, modules)
- Pipeline graph + executor tests with mock step handlers
- Agent tests with mocked Anthropic client
- **Target: 60+ tests, >80% line coverage on core + services + API**

### 0.2 Sequence Model Enhancement
- Add `embedding Vector(1536)` column via pgvector for Evo 2 embeddings
- Add `circular: bool`, `topology: enum(linear, circular)`, `organism: str`, `genbank_accession: str`
- Switch docker-compose postgres to `pgvector/pgvector:pg17` image
- Add `pgvector>=0.3` to dependencies
- Alembic migration

### 0.3 Redis for Sessions + Events
- Add Redis to docker-compose for agent session caching and pipeline event pub/sub

**Files:** `docker-compose.yml`, `pyproject.toml`, `models/sequence.py`, `tests/conftest.py`, all test files

---

## Phase 1: Assembly Domain Depth (Weeks 2-4)

*Show the intern we took their concept and went deep.*

### 1.1 Golden Gate Assembly
A fundamentally different algorithm from Gibson — uses Type IIS restriction enzymes (BsaI, BpiI) with discrete 4-bp overhang design instead of continuous boundary optimization.

**New package:** `src/bioforge/modules/assembly/core/golden_gate/`
- `enzymes.py` — `TypeIISEnzyme` dataclass with recognition site, cut offset, NEB fidelity data for BsaI, BpiI/BbsI, Esp3I/BsmBI, SapI
- `gg_solver.py` — `GoldenGateSolver`: selects 4-bp overhang sets from combinatorial space, scored by NEB Watson-Crick ligation fidelity (target >=95% all-pairs fidelity)
- `gg_constraints.py` — `LigationFidelityConstraint`, `EnzymeCompatibilityConstraint` (no internal enzyme sites in parts), `OverhangSetConstraint` (no palindromes)
- `domestication.py` — Auto-introduce silent mutations to remove internal BsaI sites, using organism-specific codon usage tables

### 1.2 Codon Optimization Engine
**New package:** `src/bioforge/modules/assembly/core/codon/`
- `tables.py` — Codon usage tables for E. coli K12, S. cerevisiae, CHO, HEK293
- `optimizer.py` — `CodonOptimizer`: protein sequence + target organism → optimized DNA. Beam search over codons with constraints: avoid rare codons (<10% freq), minimize mRNA secondary structure (sliding window folding energy), GC 40-60%, no BsaI/BpiI sites for Golden Gate compatibility
- `cai.py` — Codon Adaptation Index calculator (Sharp & Li 1987)

### 1.3 Multi-Construct Combinatorial Co-Design
- `combinatorial.py` — `CombinatorialDesigner`: input N part categories with M variants each → shared overhang set compatible across ALL N^M construct combinations. Reduces to orthogonality constraint over union of overhang sets.

### 1.4 Synthesis Provider Integration
**New package:** `src/bioforge/modules/assembly/core/synthesis/`
- `providers.py` — Abstract `SynthesisProvider` with `check_feasibility()`, `get_quote()`. Concrete: `IDTProvider` (Complexity Score API), `TwistProvider`, `GenScriptProvider`
- `feasibility.py` — Encodes real provider constraints: max fragment length (IDT gBlocks: 3000bp, eBlocks: 5000bp), GC limits (25-65%), homopolymer limits, repeat constraints. Returns per-fragment feasibility with specific failure reasons.
- `primer_ordering.py` — Generate IDT plate-format CSV for 96-well primer orders. Calculate primer Tm, check self-complementarity.

---

## Phase 2: Foundation Model Integration (Weeks 4-6)

*This is what separates a homework project from a real platform.*

### 2.1 Evo 2 Sequence Intelligence Module
**New module:** `src/bioforge/modules/evo2/`
- `client.py` — `Evo2Client` with dual backends:
  - **Local:** `evo2` Python package (7B for dev, 40B for production, requires GPU)
  - **API:** Together AI or NVIDIA BioNeMo endpoints (no local GPU needed)
  - Methods: `embed(seq) → np.ndarray`, `score_variants(seq, mutations) → list[float]`, `generate(prompt_seq, max_len) → str`
- `embeddings.py` — `EmbeddingService`: compute Evo 2 embeddings, store in pgvector, cosine similarity search, UMAP clustering
- `variant_scorer.py` — `VariantEffectPredictor`: delta log-likelihood scoring for point mutations. Positive = likely neutral/beneficial.

**Capabilities:** `evo2.embed_sequence`, `evo2.find_similar`, `evo2.score_variants`, `evo2.generate_sequence`
**Pipeline steps:** `evo2.embed`, `evo2.variant_scan`

### 2.2 Structure Prediction Module (OpenFold3)
**New module:** `src/bioforge/modules/structure/`
- `client.py` — `StructurePredictionClient` with backends: OpenFold3 local (Apache 2.0, GPU) and ESMFold API (lighter, no GPU)
- Methods: `predict_structure(seq) → PDBResult`, `predict_complex(seqs) → PDBResult`
- Store PDB files in MinIO, metadata + pLDDT scores in PostgreSQL

**Capabilities:** `structure.predict`, `structure.predict_complex`

### 2.3 Embedding-Powered Search
**New router:** `src/bioforge/api/routers/search.py`
- `POST /api/v1/search/similar` — cosine distance search in pgvector
- `POST /api/v1/search/blast` — local BLAST+ wrapper
- `GET /api/v1/search/cluster/{project_id}` — UMAP 2D projection of sequence embeddings

---

## Phase 3: Real Agent Architecture (Weeks 5-8)

*From API wrapper to reasoning engine.*

### 3.1 Multi-Turn Persistent Conversations
Rewrite `src/bioforge/agent/client.py`:
- `start_session(workspace_id, project_id) → session_id`
- `query(session_id, prompt) → AgentResponse` — loads full message history from DB, runs agentic loop with tool calls, persists everything
- New `AgentMessage` model for conversation storage

### 3.2 Domain Sub-Agents
**New:** `src/bioforge/agent/router.py` — `RouterAgent` classifies intent and delegates:
- `assembly_agent.py` — Tools: design_assembly, design_golden_gate, codon_optimize, check_feasibility. Knows Gibson vs Golden Gate selection criteria.
- `sequence_agent.py` — Tools: import, search_similar, annotate, score_variants
- `pipeline_agent.py` — Builds pipeline DAGs from natural language descriptions
- `structure_agent.py` — Tools: predict_structure, analyze_contacts. Interprets pLDDT scores.

### 3.3 Agent Memory
**New:** `src/bioforge/agent/memory.py` — `AgentMemory`:
- Short-term: conversation messages (DB-backed from 3.1)
- Long-term: `MemoryEntry` with vector embeddings in pgvector. Stores design decisions, user preferences, past outcomes.
- `remember(session_id, fact)`, `recall(query, top_k)` — auto-injected into system prompt at session start

### 3.4 Streaming Responses
**New:** `src/bioforge/agent/streaming.py` — SSE adapter using `anthropic.AsyncAnthropic().messages.stream()`. Streams tokens + tool call progress to frontend.

### 3.5 Session API
New endpoints:
- `POST /api/v1/agents/sessions` — create session
- `POST /api/v1/agents/sessions/{id}/messages` — send message
- `POST /api/v1/agents/sessions/{id}/stream` — SSE streaming
- `GET /api/v1/agents/sessions/{id}/messages` — conversation history

---

## Phase 4: Visualization Layer (Weeks 6-9)

*No CEO demo survives without visuals. No bioinformatician trusts numbers without plots.*

### 4.1 React + Next.js Frontend
**New:** `frontend/` — Next.js 15, React 19, TypeScript, Tailwind CSS, Shadcn/UI
- Auto-generated API client from FastAPI OpenAPI schema
- Streamlit UI stays as legacy/quick-demo option

### 4.2 Interactive Plasmid Map
`frontend/src/components/PlasmidMap.tsx`
- Circular SVG plasmid with feature annotation arcs (promoters, CDS, terminators, origins)
- Assembly junction markers with overhang positions
- Click-to-inspect constraint details per junction
- Fragment boundaries color-coded by feasibility
- Built on `seqviz` (Lattice Automation) or d3.js

### 4.3 Constraint Heatmap Dashboard
`frontend/src/components/ConstraintDashboard.tsx`
- Pairwise Hamming distance heatmap (green = orthogonal, red = clash)
- Per-overhang Tm bar chart with target band
- GC content profile along sequence
- Hairpin energy per overhang
- Real-time updates via SSE during optimization

### 4.4 3D Structure Viewer
`frontend/src/components/StructureViewer.tsx`
- Mol* (Molstar) wrapper — the RCSB PDB official viewer
- Color by pLDDT confidence (AlphaFold palette)
- Wild-type vs mutant side-by-side comparison

### 4.5 Agent Chat Interface
`frontend/src/app/agent/page.tsx`
- Persistent conversation threads
- Streaming token display
- Inline tool call visualization (constraint dashboards, plasmid maps inside chat)
- Drag-and-drop FASTA/GenBank file upload
- Session history sidebar

---

## Phase 5: New Modules (Weeks 8-12)

### 5.1 Sequence Alignment Module
**New:** `src/bioforge/modules/alignment/`
- `blast_runner.py` — BLAST+ CLI wrapper (blastn, blastp, tblastx), local DB management in MinIO
- `minimap2_runner.py` — Long-read alignment, PAF/SAM output
- `msa.py` — Multiple sequence alignment via MUSCLE5 or Clustal Omega

### 5.2 Variant Analysis Module
**New:** `src/bioforge/modules/variants/`
- `caller.py` — VCF parsing via cyvcf2, variant annotation from GenBank features
- `effects.py` — Synonymous/nonsynonymous/frameshift classification + Evo 2 variant scoring integration

### 5.3 Experiment Tracking Module
**New:** `src/bioforge/modules/experiments/`
- `models.py` — `Experiment`, `ExperimentStep`, `PlateLayout`, `Order` ORM models
- `protocols.py` — Template library: Gibson Assembly (NEB HiFi), Golden Gate (BsaI), bacterial transformation, colony PCR
- `ordering.py` — IDT plate-format CSV export, synthesis order management with status tracking

### 5.4 SBOL Integration
**New:** `src/bioforge/modules/sbol/`
- SBOL3 import/export (Components, Features, Constraints)
- SynBioHub registry search for standard parts (promoters, RBS, terminators)

---

## Phase 6: Pipeline + MCP Maturation (Weeks 10-13)

### 6.1 Workflow Templates
Pre-built pipelines in `src/bioforge/pipeline_engine/templates/`:
- `assembly_to_order` — sequence → codon optimize → design → feasibility check → primer order
- `variant_analysis` — VCF → annotate → Evo 2 effect prediction → summary
- `sequence_characterization` — sequence → BLAST → Evo 2 embedding → similar retrieval → structure prediction
- `library_design` — combinatorial parts → co-design → per-construct plans → batch order

### 6.2 Dynamic MCP Registration
Rewrite `mcp/server.py` to auto-register all module tools via `ModuleRegistry.all_mcp_tools()` — any new module automatically gets MCP exposure.

### 6.3 MCP Resources
- `bioforge://sequences/{id}`, `bioforge://assemblies/{id}`, `bioforge://experiments/{id}`

### 6.4 Pipeline Event Streaming
Executor emits SSE events: `on_step_start`, `on_step_complete`, `on_step_error` for real-time monitoring in the React frontend.

### 6.5 Visual Pipeline Editor
`frontend/src/app/pipelines/page.tsx` — React Flow drag-and-drop DAG editor. Users connect step nodes, configure parameters, submit to API.

---

## Implementation Timeline

```
Week  1-2   Phase 0: Tests, pgvector, schema hardening
Week  2-4   Phase 1: Golden Gate, codon opt, combinatorial, synthesis
Week  4-6   Phase 2: Evo 2, OpenFold3, embedding search
Week  5-8   Phase 3: Agent rewrite (multi-turn, sub-agents, memory, streaming)
Week  6-9   Phase 4: React frontend, plasmid map, constraint viz, structure viewer
Week  8-12  Phase 5: Alignment, variants, experiments, SBOL modules
Week 10-13  Phase 6: Pipeline templates, dynamic MCP, visual editor
```

Phases 1 + 2 parallelize (different contributors). Phase 3 depends on Phase 0 (DB) and Phase 1 (new tools). Phase 4 depends on Phase 2 (structure viewer) and Phase 3 (chat UI). Phases 5 + 6 are independent per-module work.

---

## New Dependencies

```toml
# Foundation models
"evo2>=0.2",              # DNA foundation model (optional, GPU)
"together>=1.0",          # Together AI API for Evo 2
"openfold>=3.0",          # Structure prediction (optional, GPU)

# Bioinformatics
"sbol3>=1.0",             # SBOL3 standard
"cyvcf2>=0.31",           # VCF parsing
"pysam>=0.22",            # BAM/SAM handling

# Vector search
"pgvector>=0.3",          # pgvector for embeddings

# Clustering/viz
"scikit-learn>=1.5",      # UMAP, clustering

# Agent
"redis[hiredis]>=5.0",   # Session caching, pub/sub
```

---

## Testing Strategy

| Layer | Target Tests | Coverage |
|-------|-------------|----------|
| Assembly core (existing + Golden Gate + codon) | 40 | 95% |
| Evo 2 module (mocked inference) | 20 | 80% |
| Structure module (mocked prediction) | 10 | 80% |
| Agent multi-turn + sub-agents | 25 | 85% |
| Pipeline engine + templates | 20 | 90% |
| API endpoints (all routers) | 40 | 85% |
| Services layer | 25 | 85% |
| Alignment + Variants modules | 20 | 80% |
| **Total** | **200+** | **>80%** |

---

## Why This Impresses the Intern

1. **Their assembly work is the nucleus, not a toy.** Golden Gate, codon optimization, combinatorial co-design, and synthesis ordering transform their Gibson solver into a tool that could actually run in a lab. The `BaseConstraint` → `CompositeConstraint` pattern they inspired becomes the template for every new constraint class across modules.

2. **Foundation models are real, not aspirational.** Evo 2 embeddings power similarity search. Variant scoring uses log-likelihood ratios from a 40B parameter model trained on 9 trillion base pairs. Structure prediction uses OpenFold3 (open-source AlphaFold3). These produce results a biologist would actually trust.

3. **The agent becomes worth talking to.** Multi-turn memory means it remembers your last three assembly designs. Sub-agents have real domain expertise. Streaming responses show the reasoning in real-time. Tool call visualization renders constraint heatmaps inline in the chat. This isn't ChatGPT with a biology prompt.

4. **Wet-lab grounding proves you understand the domain.** Primer ordering in IDT plate format. Synthesis feasibility against real provider constraints. Experiment tracking with protocol templates. SBOL import/export for iGEM interoperability. These features signal: we know what happens after the computation.

5. **The module system delivers on its promise.** V1 had one module. V2 has six — all automatically registered, all exposing capabilities + pipeline steps + MCP tools through the same clean `BioForgeModule` interface. Adding module #7 takes a day, not a week.

6. **The visualization sells it.** Interactive plasmid maps with assembly junctions. Constraint heatmaps that update in real-time. 3D structure predictions colored by confidence. A chat interface where the agent renders its results inline. This is what makes a CEO say "ship it" and an intern say "I want to work here."
