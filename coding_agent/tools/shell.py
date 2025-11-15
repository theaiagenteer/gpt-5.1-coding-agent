import asyncio
import contextlib
import logging
import os
import re
import shlex
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from agents import (
    ShellCallOutcome,
    ShellCommandOutput,
    ShellCommandRequest,
    ShellResult,
    ShellTool,
)


DEFAULT_COMMAND_TIMEOUT_SECONDS = 120.0
DEFAULT_INACTIVITY_TIMEOUT_SECONDS = 20.0
INACTIVITY_POLL_INTERVAL_SECONDS = 0.25

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ProcessRunResult:
    stdout: bytes
    stderr: bytes
    exit_code: int | None
    timed_out: bool
    timeout_reason: str | None = None


class ShellExecutor:
    """Executes shell commands with optional approval."""

    def __init__(
        self,
        cwd: Path | None = None,
        default_timeout: float | None = None,
        background_on_timeout: bool | None = None,
        env_overrides: dict[str, str] | None = None,
        force_non_interactive: bool | None = None,
        react_compiler_preference: str | None = None,
        inactivity_timeout: float | None = None,
    ):
        self.cwd = Path(cwd or Path.cwd())
        if default_timeout is None:
            env_timeout = os.environ.get("CODING_AGENT_SHELL_TIMEOUT_SECONDS")
            if env_timeout:
                try:
                    default_timeout = float(env_timeout)
                except ValueError:
                    default_timeout = None
        if default_timeout is None:
            default_timeout = DEFAULT_COMMAND_TIMEOUT_SECONDS
        elif default_timeout <= 0:
            default_timeout = None
        self.default_timeout = default_timeout

        if background_on_timeout is None:
            background_on_timeout = (
                os.environ.get("CODING_AGENT_SHELL_BACKGROUND_ON_TIMEOUT", "0") == "1"
            )
        self.background_on_timeout = background_on_timeout
        self.env_overrides = env_overrides.copy() if env_overrides else {}

        if force_non_interactive is None:
            force_non_interactive = (
                os.environ.get("CODING_AGENT_SHELL_FORCE_NON_INTERACTIVE", "1") == "1"
            )
        self.force_non_interactive = force_non_interactive

        if react_compiler_preference is None:
            react_compiler_preference = os.environ.get(
                "CODING_AGENT_SHELL_REACT_COMPILER", "no"
            )
        react_compiler_preference = react_compiler_preference.strip().lower()
        if react_compiler_preference not in {"use", "no"}:
            react_compiler_preference = "no"
        self.react_compiler_preference = react_compiler_preference

        if inactivity_timeout is None:
            env_inactivity = os.environ.get(
                "CODING_AGENT_SHELL_INACTIVITY_TIMEOUT_SECONDS"
            )
            if env_inactivity:
                try:
                    inactivity_timeout = float(env_inactivity)
                except ValueError:
                    inactivity_timeout = None
        if inactivity_timeout is None:
            inactivity_timeout = DEFAULT_INACTIVITY_TIMEOUT_SECONDS
        elif inactivity_timeout <= 0:
            inactivity_timeout = None
        self.inactivity_timeout = inactivity_timeout

        if self.force_non_interactive:
            # Encourage common CLIs (npm, npx, yarn, pnpm, etc.) to auto-select defaults and
            # skip prompts by setting environment variables they respect.
            self.env_overrides.setdefault("CI", "1")
            self.env_overrides.setdefault("npm_config_yes", "true")
            self.env_overrides.setdefault("NPX_YES", "1")
            self.env_overrides.setdefault("HUSKY_SKIP_HOOKS", "1")
            self.env_overrides.setdefault("YARN_ENABLE_IMMUTABLE_INSTALLS", "false")
            self.env_overrides.setdefault("SKIP_PROMPTS", "1")

    async def __call__(self, request: ShellCommandRequest) -> ShellResult:
        action = request.data.action

        outputs: list[ShellCommandOutput] = []
        for command in action.commands:
            env = os.environ.copy()
            env.update(self.env_overrides)
            prepared_command = self._prepare_command(command)

            if self._requires_background(prepared_command):
                if not self._is_backgrounded(prepared_command):
                    message = (
                        "Command appears to start a long-running dev server or watcher. "
                        "Always run such commands in the background by appending ' &' "
                        "(for example 'npm run dev &' or 'uvicorn app:app --reload &')."
                    )
                    outputs.append(
                        ShellCommandOutput(
                            command=prepared_command,
                            stdout="",
                            stderr=message,
                            outcome=ShellCallOutcome(type="exit", exit_code=1),
                        )
                    )
                    continue
                outputs.append(
                    await self._spawn_detached_background(prepared_command, env)
                )
                continue

            timeout = None
            if action.timeout_ms is not None:
                timeout = max(action.timeout_ms / 1000, 0)
            elif self.default_timeout is not None:
                timeout = self.default_timeout

            result = await self._execute_with_watchdogs(
                prepared_command,
                env,
                timeout,
            )

            stdout = result.stdout.decode("utf-8", errors="ignore")
            stderr = result.stderr.decode("utf-8", errors="ignore")
            outputs.append(
                ShellCommandOutput(
                    command=prepared_command,
                    stdout=stdout,
                    stderr=stderr,
                    outcome=ShellCallOutcome(
                        type="timeout" if result.timed_out else "exit",
                        exit_code=result.exit_code,
                    ),
                )
            )

            if result.timed_out:
                break

        return ShellResult(
            output=outputs,
            provider_data={"working_directory": str(self.cwd)},
        )

    _YES_FLAG_PATTERNS = (
        r"\bnpm\s+init\b",
        r"\bnpm\s+create\b",
        r"\bnpx\s+[^ ]*create",
        r"\byarn\s+create\b",
        r"\bpnpm\s+create\b",
    )
    _AUTO_CONFIRM_PATTERNS = (
        r"\bpython\s+manage\.py\s+migrate\b",
        r"\bpython\s+manage\.py\s+makemigrations\b",
        r"\bdjango-admin\s+migrate\b",
        r"\bdjango-admin\s+makemigrations\b",
        r"\bnpx\s+expo\b",
        r"\bexpo\s+(init|start)\b",
        r"\bpnpm\s+dlx\s+[^ ]*create\b",
        r"\bnpx\s+[^ ]*create-[^ ]+\b",
    )
    _VITE_CREATE_PATTERNS = (
        r"\bnpm\s+create\s+vite(@latest)?\b",
        r"\bnpx\s+create-vite\b",
        r"\bpnpm\s+create\s+vite(@latest)?\b",
    )
    _DEV_SERVER_PATTERNS = (
        r"\bnpm\s+run\s+(dev|start|preview|serve|storybook)\b",
        r"\bnpm\s+run\s+.*(--watch|--serve)\b",
        r"\bnpx\s+next\s+dev\b",
        r"\bnext\s+dev\b",
        r"\bvite\s+dev\b",
        r"\bnpx\s+vite\s+dev\b",
        r"\bpnpm\s+(dev|preview|start|serve)\b",
        r"\byarn\s+(dev|start|preview|serve|storybook)\b",
        r"\bnpx\s+astro\s+dev\b",
        r"\bnpx\s+remix\s+dev\b",
        r"\bnpx\s+expo\b",
        r"\bexpo\s+start\b",
        r"\buvicorn\b.+(--reload|--workers)",
        r"\bflask\s+run\b",
        r"\bdjango-admin\s+runserver\b",
        r"\bpython\s+-m\s+http\.server\b",
        r"\bnuxi\s+dev\b",
        r"\bnpx\s+nuxt\s+dev\b",
    )

    def _append_flag(self, command: str, flag: str) -> str:
        base, background = self._split_background_suffix(command)
        if " -- " in base:
            base = base.replace(" -- ", f" {flag} -- ", 1)
        else:
            base = f"{base} {flag}".strip()
        return f"{base}{background}"

    def _ensure_subcommand_flag(self, command: str, flag: str) -> str:
        base, background = self._split_background_suffix(command)
        if " -- " not in base:
            return f"{self._ensure_flag(base, flag)}{background}"
        prefix, suffix = base.split(" -- ", 1)
        suffix_lower = suffix.lower()
        if self._flag_present(suffix_lower, flag):
            return command
        new_suffix = f"{flag} {suffix}".lstrip()
        return f"{prefix} -- {new_suffix}{background}"

    def _flag_present(self, command_lower: str, flag: str) -> bool:
        base, _ = self._split_background_suffix(command_lower)
        return re.search(rf"(?:^|\s){re.escape(flag)}(?:\s|$)", base) is not None

    def _ensure_flag(self, command: str, flag: str) -> str:
        if self._flag_present(command.lower(), flag):
            return command
        return self._append_flag(command, flag)

    @staticmethod
    def _split_background_suffix(command: str) -> tuple[str, str]:
        stripped = command.rstrip()
        if stripped.endswith("&"):
            base = stripped[:-1].rstrip()
            return base, " &"
        return command, ""

    def _has_yes_flag(self, command_lower: str) -> bool:
        return " --yes" in command_lower or " -y" in command_lower

    def _prepare_command(self, command: str) -> str:
        prepared = command.strip()
        lower = prepared.lower()

        if self.force_non_interactive:
            if not self._has_yes_flag(lower):
                for pattern in self._YES_FLAG_PATTERNS:
                    if re.search(pattern, lower):
                        prepared = self._append_flag(prepared, "--yes")
                        lower = prepared.lower()
                        break

            if "create-next-app" in lower and "--use-react-compiler" not in lower and "--no-use-react-compiler" not in lower:
                compiler_flag = (
                    "--use-react-compiler" if self.react_compiler_preference == "use" else "--no-use-react-compiler"
                )
                prepared = self._append_flag(prepared, compiler_flag)

            prepared = self._auto_confirm_interactive(prepared, lower)
            lower = prepared.lower()
            for pattern in self._VITE_CREATE_PATTERNS:
                if re.search(pattern, lower):
                    prepared = self._ensure_subcommand_flag(prepared, "--no-rolldown")
                    prepared = self._ensure_subcommand_flag(prepared, "--no-interactive")
                    lower = prepared.lower()
                    break

        if self.force_non_interactive and self._requires_background(prepared):
            if self._is_backgrounded(prepared):
                prepared = self._wrap_background_command(prepared)

        return prepared
    def _wrap_background_command(self, command: str) -> str:
        """
        Ensure background commands detach immediately so /bin/sh -c doesn't wait
        for the job to finish.
        """
        parts = command.split("&&")
        detached_parts: list[str] = []

        for idx, part in enumerate(parts):
            stripped = part.strip()
            if idx == len(parts) - 1 and self._is_backgrounded(stripped):
                body = stripped.rstrip()
                if body.endswith("&"):
                    body = body[:-1].rstrip()

                detached = (
                    "(trap '' HUP; setsid sh -c "
                    f"{shlex.quote(body)} >/dev/null 2>&1 &) && echo $!"
                )
                detached_parts.append(detached)
            else:
                detached_parts.append(part)

        return " && ".join(detached_parts)

    async def _spawn_detached_background(
        self, command: str, env: dict[str, str]
    ) -> ShellCommandOutput:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=self.cwd,
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        asyncio.create_task(self._reap_background_process(proc))
        return ShellCommandOutput(
            command=command,
            stdout=f"Detached background command (pid={proc.pid}).",
            stderr="",
            outcome=ShellCallOutcome(type="exit", exit_code=0),
        )

    def _requires_background(self, command: str) -> bool:
        normalized = command.strip().lower()
        for pattern in self._DEV_SERVER_PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    def _is_backgrounded(self, command: str) -> bool:
        stripped = command.rstrip()
        if stripped.endswith("&"):
            return True
        if self._has_inline_background_operator(stripped):
            return True
        if "nohup " in stripped and "&" in stripped:
            return True
        return False

    @staticmethod
    def _has_inline_background_operator(command: str) -> bool:
        for idx, char in enumerate(command):
            if char != "&":
                continue
            prev = command[idx - 1] if idx > 0 else ""
            nxt = command[idx + 1] if idx + 1 < len(command) else ""
            if prev == "&":
                continue
            if prev == ">":
                continue
            if nxt == ">":
                continue
            if prev.isspace() and (not nxt or nxt.isspace()):
                return True
        return False

    def _auto_confirm_interactive(self, command: str, command_lower: str) -> str:
        if self._starts_with_yes_pipe(command):
            return command
        for pattern in self._AUTO_CONFIRM_PATTERNS:
            if re.search(pattern, command_lower):
                return f"yes | {command}"
        return command

    def _starts_with_yes_pipe(self, command: str) -> bool:
        stripped = command.lstrip()
        return stripped.startswith("yes |")

    async def _execute_with_watchdogs(
        self, command: str, env: dict[str, str], timeout: float | None
    ) -> _ProcessRunResult:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=self.cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._monitor_process(proc, command, timeout)

    async def _monitor_process(
        self,
        proc: asyncio.subprocess.Process,
        command: str,
        timeout: float | None,
    ) -> _ProcessRunResult:
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        last_activity = time.monotonic()

        def mark_activity() -> None:
            nonlocal last_activity
            last_activity = time.monotonic()

        stdout_task = asyncio.create_task(
            self._pump_stream(proc.stdout, stdout_chunks, mark_activity)
        )
        stderr_task = asyncio.create_task(
            self._pump_stream(proc.stderr, stderr_chunks, mark_activity)
        )

        wait_task = asyncio.create_task(proc.wait())
        timeout_task: asyncio.Task[None] | None = None
        if timeout is not None:
            timeout_task = asyncio.create_task(asyncio.sleep(timeout))

        inactivity_task: asyncio.Task[bool] | None = None
        if self.inactivity_timeout is not None:
            async def _watch_inactivity() -> bool:
                while True:
                    await asyncio.sleep(INACTIVITY_POLL_INTERVAL_SECONDS)
                    if (
                        time.monotonic() - last_activity
                        > self.inactivity_timeout
                    ):
                        return True

            inactivity_task = asyncio.create_task(_watch_inactivity())

        timed_out = False
        inactivity_triggered = False
        background_detached = False

        while True:
            pending: set[asyncio.Task[object]] = {wait_task}
            if timeout_task is not None:
                pending.add(timeout_task)
            if inactivity_task is not None:
                pending.add(inactivity_task)

            done, _ = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            if wait_task in done:
                break

            if timeout_task and timeout_task in done:
                timed_out = True
                if self.background_on_timeout:
                    background_detached = True
                    break
                proc.kill()
                await wait_task
                break

            if inactivity_task and inactivity_task in done:
                inactivity_triggered = True
                proc.kill()
                await wait_task
                break

        for task in (timeout_task, inactivity_task):
            if task is not None and not task.done():
                task.cancel()
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        if background_detached and not wait_task.done():
            wait_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await wait_task
            asyncio.create_task(self._reap_background_process(proc))
        elif not wait_task.done():
            await wait_task

        if background_detached:
            for task in (stdout_task, stderr_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            stdout_bytes = b""
            stderr_bytes = b"".join(stderr_chunks)
        else:
            await stdout_task
            await stderr_task
            stdout_bytes = b"".join(stdout_chunks)
            stderr_bytes = b"".join(stderr_chunks)

        exit_code = proc.returncode
        message: str | None = None
        timeout_reason: str | None = None
        timed_out_event = inactivity_triggered or timed_out

        if inactivity_triggered and self.inactivity_timeout is not None:
            timeout_reason = "inactivity"
            message = (
                f"Command produced no output for {self.inactivity_timeout} seconds "
                f"and was terminated (pid={proc.pid})."
            )
        elif timed_out:
            timeout_reason = (
                "duration_background" if background_detached else "duration"
            )
            timeout_value = (
                f"{timeout}"
                if timeout is not None
                else "the configured timeout"
            )
            if background_detached:
                message = (
                    f"Command exceeded timeout of {timeout_value} seconds and is still "
                    f"running in the background (pid={proc.pid})."
                )
            else:
                message = (
                    f"Command exceeded timeout of {timeout_value} seconds and was "
                    f"terminated (pid={proc.pid})."
                )

        if message:
            encoded = message.encode("utf-8")
            if stderr_bytes:
                stderr_bytes = stderr_bytes + b"\n" + encoded
            else:
                stderr_bytes = encoded

        if timed_out_event:
            logger.warning(
                "Command '%s' timed out (%s).", command, timeout_reason
            )
        else:
            logger.debug(
                "Command '%s' completed with exit code %s.",
                command,
                exit_code,
            )

        return _ProcessRunResult(
            stdout=stdout_bytes,
            stderr=stderr_bytes,
            exit_code=exit_code,
            timed_out=timed_out_event,
            timeout_reason=timeout_reason,
        )

    async def _pump_stream(
        self,
        stream: asyncio.StreamReader | None,
        container: list[bytes],
        mark_activity: Callable[[], None],
    ) -> None:
        if stream is None:
            return
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            container.append(chunk)
            mark_activity()

    async def _reap_background_process(
        self, proc: asyncio.subprocess.Process
    ) -> None:
        try:
            await proc.wait()
            logger.debug(
                "Background process (pid=%s) exited with %s.",
                proc.pid,
                proc.returncode,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "Failed to reap background process (pid=%s).", proc.pid
            )

workspace_path = Path("./mnt").resolve()
shell_tool = ShellTool(executor=ShellExecutor(cwd=workspace_path))