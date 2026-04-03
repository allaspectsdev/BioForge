"""Docker container runner for pipeline steps using BioContainers."""

import asyncio
from typing import Any


async def run_docker(
    image: str,
    command: list[str],
    volumes: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 3600,
) -> dict[str, Any]:
    """Run a command in a Docker container."""
    docker_cmd = ["docker", "run", "--rm"]

    if volumes:
        for host_path, container_path in volumes.items():
            docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

    if env:
        for key, value in env.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

    docker_cmd.append(image)
    docker_cmd.extend(command)

    proc = await asyncio.create_subprocess_exec(
        *docker_cmd,
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
            "stderr": f"Docker container timed out after {timeout}s",
        }

    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode() if stdout else "",
        "stderr": stderr.decode() if stderr else "",
    }
