import asyncio
import shlex
import sys
from pathlib import Path

import pytest

from agents import (
    ShellActionRequest,
    ShellCallData,
    ShellCallOutcome,
    ShellCommandOutput,
    ShellCommandRequest,
    ShellResult,
)
from coding_agent.tools.shell import ShellExecutor


def _build_request(command: str) -> ShellCommandRequest:
    action = ShellActionRequest(commands=[command], timeout_ms=None)
    call_data = ShellCallData(call_id="test_call", action=action)
    return ShellCommandRequest(ctx_wrapper=None, data=call_data)  # type: ignore[arg-type]


def test_executor_assigns_fallback_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODING_AGENT_SHELL_TIMEOUT_SECONDS", raising=False)
    executor = ShellExecutor(cwd=tmp_path)
    assert executor.default_timeout == pytest.approx(120.0)


def test_prepare_command_auto_confirms_django_migrate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT_SHELL_FORCE_NON_INTERACTIVE", "1")
    executor = ShellExecutor(cwd=tmp_path)
    prepared = executor._prepare_command("python manage.py migrate")
    assert prepared.startswith("yes | ")


def test_inactivity_timeout_kills_silent_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        monkeypatch.delenv("CODING_AGENT_SHELL_TIMEOUT_SECONDS", raising=False)
        command = f'{shlex.quote(sys.executable)} -c "import time; time.sleep(2)"'
        executor = ShellExecutor(
            cwd=tmp_path,
            default_timeout=10,
            background_on_timeout=False,
            inactivity_timeout=0.5,
        )
        result = await executor(_build_request(command))
        output = result.output[0]
        assert "no output" in output.stderr.lower()
        assert output.outcome.type == "timeout"

    asyncio.run(_run())


def test_prepare_command_disables_vite_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODING_AGENT_SHELL_FORCE_NON_INTERACTIVE", "1")
    executor = ShellExecutor(cwd=tmp_path)
    command = "npm create vite@latest portfolio -- --template react-swc-ts"
    prepared = executor._prepare_command(command)
    assert "--no-interactive" in prepared
    assert "--no-rolldown" in prepared
    yes_index = prepared.index("--yes")
    template_index = prepared.index("--template")
    assert yes_index < template_index
    _, args = prepared.split(" -- ", 1)
    assert args.startswith("--no-interactive")
    assert "--no-rolldown" in args.split()


def test_background_suffix_preserved_when_appending_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODING_AGENT_SHELL_FORCE_NON_INTERACTIVE", "1")
    executor = ShellExecutor(cwd=tmp_path)
    command = "npm create vite@latest portfolio &"
    prepared = executor._prepare_command(command)
    assert prepared.endswith(" &")
    assert "--no-interactive" in prepared
    assert "--no-rolldown" in prepared


def test_is_backgrounded_detects_inline_background_operator(tmp_path: Path) -> None:
    executor = ShellExecutor(cwd=tmp_path)
    command = (
        "cd portfolio && npm run dev -- --host 0.0.0.0 --port 4173 "
        ">/tmp/portfolio-dev.log 2>&1 & echo $!"
    )
    assert executor._is_backgrounded(command) is True


def test_executor_spawns_detached_background(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT_SHELL_FORCE_NON_INTERACTIVE", "1")
    executor = ShellExecutor(cwd=tmp_path)

    recorded: dict[str, str] = {}

    async def fake_spawn(self, command: str, env: dict[str, str]) -> ShellCommandOutput:
        recorded["command"] = command
        return ShellCommandOutput(
            command=command,
            stdout="detached",
            stderr="",
            outcome=ShellCallOutcome(type="exit", exit_code=0),
        )

    monkeypatch.setattr(ShellExecutor, "_spawn_detached_background", fake_spawn)

    async def _run() -> ShellResult:
        request = _build_request(
            "npm run dev -- --host 0.0.0.0 --port 4173 >/tmp/log 2>&1 & echo $!"
        )
        return await executor(request)

    result = asyncio.run(_run())
    assert recorded["command"].endswith("& echo $!")
    assert result.output[0].stdout == "detached"

