from pydantic import BaseModel, Field


class AssemblyConstraints(BaseModel):
    min_fragment_bp: int = Field(default=2000, ge=500, le=10000)
    max_fragment_bp: int = Field(default=2500, ge=500, le=15000)
    overhang_length: int = Field(default=25, ge=15, le=40)
    min_tm: float = Field(default=50.0, ge=30.0, le=80.0)
    max_tm: float = Field(default=65.0, ge=30.0, le=80.0)
    min_gc: float = Field(default=0.40, ge=0.0, le=1.0)
    max_gc: float = Field(default=0.60, ge=0.0, le=1.0)
    min_hamming_distance: int = Field(default=5, ge=1, le=15)
    min_ddg_kcal: float = Field(default=4.0, ge=0.0, le=20.0)
    max_homopolymer_length: int = Field(default=4, ge=2, le=10)


class AssemblyRequest(BaseModel):
    sequence: str = Field(description="DNA sequence string")
    constraints: AssemblyConstraints = Field(default_factory=AssemblyConstraints)
    circular: bool = False
    seed: int | None = None


class FragmentResult(BaseModel):
    index: int
    start: int
    end: int
    length: int


class OverhangResult(BaseModel):
    index: int
    position: int
    sequence: str
    length: int
    tm: float
    gc: float
    homopolymer_run: int


class AssemblyResult(BaseModel):
    feasible: bool
    num_fragments: int
    fragments: list[FragmentResult]
    overhangs: list[OverhangResult]
    quality_scores: dict
    restarts_used: int
    total_time_s: float
    violations: list[dict] = Field(default_factory=list)
