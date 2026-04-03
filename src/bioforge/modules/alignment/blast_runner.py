"""BLAST+ CLI wrapper and mock runner for testing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from bioforge.modules.alignment.schemas import (
    BlastHit,
    BlastHSP,
    BlastResult,
    BlastSearchRequest,
)

logger = logging.getLogger(__name__)


class BaseBlastRunner(ABC):
    """Abstract base class for BLAST runners."""

    @abstractmethod
    async def search(self, request: BlastSearchRequest) -> BlastResult:
        """Run a BLAST search and return structured results."""
        ...

    @abstractmethod
    async def create_db(
        self,
        fasta_path: str,
        db_name: str,
        db_type: str = "nucl",
    ) -> dict[str, Any]:
        """Create a BLAST database from a FASTA file."""
        ...


class BlastRunner(BaseBlastRunner):
    """Production BLAST+ CLI wrapper.

    Requires BLAST+ to be installed and available on PATH.
    Uses makeblastdb for database creation and blastn/blastp for searches.
    """

    def __init__(self, db_dir: str | None = None) -> None:
        self.db_dir = Path(db_dir) if db_dir else Path(tempfile.gettempdir()) / "bioforge_blast_dbs"
        self.db_dir.mkdir(parents=True, exist_ok=True)

    async def create_db(
        self,
        fasta_path: str,
        db_name: str,
        db_type: str = "nucl",
    ) -> dict[str, Any]:
        """Create a BLAST database using makeblastdb.

        Args:
            fasta_path: Path to input FASTA file.
            db_name: Name for the database.
            db_type: Database type ('nucl' or 'prot').

        Returns:
            Dict with database path and status.
        """
        out_path = self.db_dir / db_name
        cmd = [
            "makeblastdb",
            "-in", fasta_path,
            "-dbtype", db_type,
            "-out", str(out_path),
            "-parse_seqids",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode().strip(),
                    "db_path": str(out_path),
                }

            return {
                "success": True,
                "db_path": str(out_path),
                "message": stdout.decode().strip(),
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "makeblastdb not found. Is BLAST+ installed?",
                "db_path": str(out_path),
            }

    async def search(self, request: BlastSearchRequest) -> BlastResult:
        """Run a BLAST search using the BLAST+ CLI.

        Writes the query to a temp file, runs the appropriate blast program,
        and parses JSON output.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fasta", delete=False
        ) as qf:
            qf.write(f">query\n{request.query_sequence}\n")
            query_path = qf.name

        cmd = [
            request.program,
            "-query", query_path,
            "-db", request.database,
            "-evalue", str(request.evalue_threshold),
            "-max_target_seqs", str(request.max_hits),
            "-outfmt", "15",  # JSON output
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error("BLAST search failed: %s", stderr.decode())
                return BlastResult(
                    program=request.program,
                    database=request.database,
                    query_length=len(request.query_sequence),
                )

            return self._parse_json_output(
                stdout.decode(), request.program, request.database, len(request.query_sequence)
            )
        except FileNotFoundError:
            logger.error("%s not found. Is BLAST+ installed?", request.program)
            return BlastResult(
                program=request.program,
                database=request.database,
                query_length=len(request.query_sequence),
            )
        finally:
            Path(query_path).unlink(missing_ok=True)

    @staticmethod
    def _parse_json_output(
        raw_json: str,
        program: str,
        database: str,
        query_length: int,
    ) -> BlastResult:
        """Parse BLAST+ JSON output (outfmt 15) into BlastResult."""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return BlastResult(
                program=program, database=database, query_length=query_length
            )

        hits: list[BlastHit] = []
        report = data.get("BlastOutput2", [{}])
        if isinstance(report, list) and report:
            search = report[0].get("report", {}).get("results", {}).get("search", {})
            for hit_data in search.get("hits", []):
                hsps = []
                for hsp in hit_data.get("hsps", []):
                    hsps.append(
                        BlastHSP(
                            query_start=hsp.get("query_from", 0),
                            query_end=hsp.get("query_to", 0),
                            subject_start=hsp.get("hit_from", 0),
                            subject_end=hsp.get("hit_to", 0),
                            identity_pct=round(
                                hsp.get("identity", 0) / max(hsp.get("align_len", 1), 1) * 100, 1
                            ),
                            e_value=hsp.get("evalue", 0),
                            bit_score=hsp.get("bit_score", 0),
                            alignment_length=hsp.get("align_len", 0),
                            gaps=hsp.get("gaps", 0),
                            query_aligned=hsp.get("qseq", ""),
                            subject_aligned=hsp.get("hseq", ""),
                        )
                    )
                desc = hit_data.get("description", [{}])
                first_desc = desc[0] if desc else {}
                best_hsp = min(hsps, key=lambda h: h.e_value) if hsps else None
                hits.append(
                    BlastHit(
                        subject_id=first_desc.get("accession", ""),
                        subject_description=first_desc.get("title", ""),
                        subject_length=hit_data.get("len", 0),
                        hsps=hsps,
                        best_evalue=best_hsp.e_value if best_hsp else 0,
                        best_identity_pct=best_hsp.identity_pct if best_hsp else 0,
                    )
                )

        return BlastResult(
            program=program,
            database=database,
            query_length=query_length,
            hits=hits,
            total_hits=len(hits),
        )


class MockBlastRunner(BaseBlastRunner):
    """Mock BLAST runner for testing.

    Generates deterministic but realistic-looking BLAST hits based
    on the query sequence, suitable for unit tests and demos.
    """

    def __init__(self, num_hits: int = 5) -> None:
        self.num_hits = num_hits

    async def create_db(
        self,
        fasta_path: str,
        db_name: str,
        db_type: str = "nucl",
    ) -> dict[str, Any]:
        """Mock database creation -- always succeeds."""
        return {
            "success": True,
            "db_path": f"/tmp/mock_blast_dbs/{db_name}",
            "message": f"Mock database '{db_name}' created from {fasta_path}",
        }

    async def search(self, request: BlastSearchRequest) -> BlastResult:
        """Generate mock BLAST hits.

        Uses a hash of the query to seed the random generator for
        deterministic results.
        """
        seed = int(hashlib.md5(request.query_sequence.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        query_len = len(request.query_sequence)

        hits: list[BlastHit] = []
        organisms = [
            "Escherichia coli K-12",
            "Saccharomyces cerevisiae S288C",
            "Homo sapiens",
            "Bacillus subtilis 168",
            "Arabidopsis thaliana",
            "Drosophila melanogaster",
            "Mus musculus",
            "Caenorhabditis elegans",
        ]

        for i in range(min(self.num_hits, request.max_hits)):
            identity = rng.uniform(60.0, 99.5) - (i * 5)
            identity = max(30.0, identity)
            align_len = int(query_len * rng.uniform(0.5, 1.0))
            q_start = rng.randint(1, max(1, query_len - align_len))
            s_start = rng.randint(1, 5000)
            e_value = 10 ** (-rng.uniform(5, 50) + i * 5)
            bit_score = rng.uniform(50, 500) - (i * 30)
            gaps = rng.randint(0, max(1, align_len // 20))
            organism = rng.choice(organisms)
            accession = f"MOCK_{i+1:04d}"

            hsp = BlastHSP(
                query_start=q_start,
                query_end=q_start + align_len - 1,
                subject_start=s_start,
                subject_end=s_start + align_len - 1,
                identity_pct=round(identity, 1),
                e_value=e_value,
                bit_score=round(max(bit_score, 20), 1),
                alignment_length=align_len,
                gaps=gaps,
            )

            hits.append(
                BlastHit(
                    subject_id=accession,
                    subject_description=f"hypothetical protein [{organism}]",
                    subject_length=rng.randint(align_len, align_len * 3),
                    hsps=[hsp],
                    best_evalue=e_value,
                    best_identity_pct=round(identity, 1),
                )
            )

        return BlastResult(
            program=request.program,
            database=request.database,
            query_length=query_len,
            hits=hits,
            total_hits=len(hits),
            search_time_s=round(rng.uniform(0.1, 2.0), 3),
        )
