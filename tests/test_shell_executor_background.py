import asyncio
import shlex
import sys
from pathlib import Path

import pytest

from agents import ShellActionRequest, ShellCallData, ShellCommandRequest
from coding_agent.tools.shell import ShellExecutor


def _build_request(command: str, timeout_ms: int) -> ShellCommandRequest:
    action = ShellActionRequest(commands=[command], timeout_ms=timeout_ms)
    call_data = ShellCallData(call_id="test_background", action=action)
    return ShellCommandRequest(ctx_wrapper=None, data=call_data)  # type: ignore[arg-type]


def test_background_process_survives_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Ensure long-running commands that exceed the timeout continue running
    in the background and finish their work.
    """

    async def _run() -> None:
        marker_file = tmp_path / "shell_executor_background_marker.txt"
        command = (
            f"{shlex.quote(sys.executable)} -c \"import time, pathlib; "
            f"time.sleep(2); pathlib.Path(r'{marker_file.as_posix()}').write_text('done')\""
        )

        monkeypatch.setenv("CODING_AGENT_SHELL_BACKGROUND_ON_TIMEOUT", "1")
        executor = ShellExecutor(cwd=tmp_path)

        await executor(_build_request(command, timeout_ms=500))

        # Allow time for the background process to finish and write the marker file.
        await asyncio.sleep(3)

        assert marker_file.exists(), "Background process did not finish after timeout."
        marker_file.unlink(missing_ok=True)

    asyncio.run(_run())
