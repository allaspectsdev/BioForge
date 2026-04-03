"""Local process runner for pipeline steps."""

import asyncio
import subprocess
from typing import Any


async def run_local_command(
    command: list[str],
    cwd: str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a command locally and return stdout/stderr."""
    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
        }

    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode() if stdout else "",
        "stderr": stderr.decode() if stderr else "",
    }
