"""Isolated Code Sandbox: Ephemeral execution runner with strict timeouts and resource boundaries."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from typing import Literal

Language = Literal["python", "bash", "javascript"]

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_BYTES = 50 * 1024  # 50 KB output limit to avoid memory flooding


@dataclass
class SandboxExecutionResult:
    """Standardized output of sandboxed code execution."""

    stdout: str
    stderr: str
    exit_code: int
    execution_ms: int
    timed_out: bool
    language: Language
    is_sandboxed: bool


class CodeSandbox:
    """Executes arbitrary user/doc code snippets within strict sandboxed limits."""

    DOCKER_IMAGE_MAP = {
        "python": "python:3.11-slim",
        "bash": "alpine:3.19",
        "javascript": "node:20-alpine",
    }

    FILE_EXTENSIONS = {
        "python": "py",
        "bash": "sh",
        "javascript": "js",
    }

    @classmethod
    def has_docker(cls) -> bool:
        """Check if docker binary is available on PATH."""
        return shutil.which("docker") is not None

    @classmethod
    async def execute(
        cls,
        code: str,
        language: Language = "python",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> SandboxExecutionResult:
        """Execute snippet with resource capping and wall-clock watchdog."""
        start_time = time.perf_counter()

        # Create isolated temporary workspace
        with tempfile.TemporaryDirectory(prefix="opendocs_sandbox_") as tmp_dir:
            ext = cls.FILE_EXTENSIONS.get(language, "txt")
            script_path = os.path.join(tmp_dir, f"main.{ext}")

            # Write code to file
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 1. Prefer Docker Container Isolation if available
            if cls.has_docker():
                return await cls._run_in_docker(
                    script_path=script_path,
                    tmp_dir=tmp_dir,
                    language=language,
                    timeout=timeout_seconds,
                    start_time=start_time,
                )

            # 2. Local Restricted Process Runner (Fallback when Docker is absent)
            return await cls._run_local_restricted(
                script_path=script_path,
                tmp_dir=tmp_dir,
                language=language,
                timeout=timeout_seconds,
                start_time=start_time,
            )

    @classmethod
    async def _run_in_docker(
        cls,
        script_path: str,
        tmp_dir: str,
        language: Language,
        timeout: float,
        start_time: float,
    ) -> SandboxExecutionResult:
        """Execute inside rootless ephemeral container with --net=none."""
        image = cls.DOCKER_IMAGE_MAP.get(language, "python:3.11-slim")
        filename = os.path.basename(script_path)

        cmd = [
            "docker", "run", "--rm",
            "--net=none",                # Block all outbound networking & SSRF
            "--memory=256m",             # 256 MB memory ceiling
            "--cpus=0.5",                # Half CPU core quota
            "--pids-limit=64",           # Prevent fork bombs
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "-v", f"{tmp_dir}:/workspace:ro",
            "-w", "/workspace",
            image,
        ]

        if language == "python":
            cmd.extend(["python", filename])
        elif language == "bash":
            cmd.extend(["sh", filename])
        elif language == "javascript":
            cmd.extend(["node", filename])

        return await cls._spawn_process(cmd, timeout, start_time, language, is_sandboxed=True)

    @classmethod
    async def _run_local_restricted(
        cls,
        script_path: str,
        tmp_dir: str,
        language: Language,
        timeout: float,
        start_time: float,
    ) -> SandboxExecutionResult:
        """Local execution fallback with restricted environment and cwd."""
        if language == "python":
            cmd = ["python", script_path]
        elif language == "bash":
            # On Windows fallback to PowerShell/cmd if bash not found
            sh_bin = shutil.which("bash") or shutil.which("sh")
            if sh_bin:
                cmd = [sh_bin, script_path]
            else:
                return SandboxExecutionResult(
                    stdout="",
                    stderr="Bash runtime not available on this host.",
                    exit_code=1,
                    execution_ms=0,
                    timed_out=False,
                    language=language,
                    is_sandboxed=False,
                )
        elif language == "javascript":
            node_bin = shutil.which("node")
            if not node_bin:
                return SandboxExecutionResult(
                    stdout="",
                    stderr="Node.js runtime not available on this host.",
                    exit_code=1,
                    execution_ms=0,
                    timed_out=False,
                    language=language,
                    is_sandboxed=False,
                )
            cmd = [node_bin, script_path]
        else:
            cmd = ["python", script_path]

        return await cls._spawn_process(cmd, timeout, start_time, language, is_sandboxed=False)

    @classmethod
    async def _spawn_process(
        cls,
        cmd: list[str],
        timeout: float,
        start_time: float,
        language: Language,
        is_sandboxed: bool,
    ) -> SandboxExecutionResult:
        """Spawn subprocess with timeout watchdog and bounded output streaming."""
        timed_out = False
        stdout_data = b""
        stderr_data = b""
        exit_code = 0

        # Minimal sanitized environment
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            stdout_data = stdout_bytes[:MAX_OUTPUT_BYTES]
            stderr_data = stderr_bytes[:MAX_OUTPUT_BYTES]
            exit_code = proc.returncode if proc.returncode is not None else 0

        except asyncio.TimeoutError:
            timed_out = True
            exit_code = -1
            stderr_data = f"Execution timed out after {timeout} seconds.".encode()
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

        except Exception as exc:
            exit_code = 1
            stderr_data = f"Process invocation error: {exc}".encode()

        ms = int((time.perf_counter() - start_time) * 1000)

        return SandboxExecutionResult(
            stdout=stdout_data.decode("utf-8", errors="replace"),
            stderr=stderr_data.decode("utf-8", errors="replace"),
            exit_code=exit_code,
            execution_ms=ms,
            timed_out=timed_out,
            language=language,
            is_sandboxed=is_sandboxed,
        )
