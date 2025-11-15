import asyncio
from pathlib import Path

import pytest

from coding_agent.tools.OpenAIImageGenerationTool import (
    ImageGenerationRequest,
    OpenAIImageGenerationTool,
)


def test_output_directory_must_be_absolute(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        OpenAIImageGenerationTool(
            output_directory="relative/path",
            requests=[ImageGenerationRequest(prompt="test prompt")],
        )


def test_run_uses_shared_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved_paths: list[Path] = []

    async def fake_generate_single_image(self, client, req, output_path, quality):
        saved_paths.append(output_path)
        return str(output_path)

    monkeypatch.setattr(
        OpenAIImageGenerationTool,
        "_generate_single_image",
        fake_generate_single_image,
    )

    tool = OpenAIImageGenerationTool(
        output_directory=str(tmp_path),
        requests=[
            ImageGenerationRequest(
                prompt="A scenic mountain landscape", filename="custom.png"
            ),
            ImageGenerationRequest(prompt="A futuristic city skyline"),
        ],
    )

    result = asyncio.run(tool.run())

    assert "Generated 2 image(s)" in result
    assert saved_paths[0] == tmp_path / "custom.png"
    assert saved_paths[1].parent == tmp_path
    assert saved_paths[1].name.startswith("image-")
    assert saved_paths[1].suffix == ".png"


def test_default_quality_is_low(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed_qualities: list[str] = []

    async def fake_generate_single_image(self, client, req, output_path, quality):
        observed_qualities.append(quality)
        return str(output_path)

    monkeypatch.setattr(
        OpenAIImageGenerationTool,
        "_generate_single_image",
        fake_generate_single_image,
    )

    tool = OpenAIImageGenerationTool(
        output_directory=str(tmp_path),
        requests=[ImageGenerationRequest(prompt="Default quality sample")],
    )

    asyncio.run(tool.run())

    assert observed_qualities == ["low"]


def test_can_override_quality(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed_qualities: list[str] = []

    async def fake_generate_single_image(self, client, req, output_path, quality):
        observed_qualities.append(quality)
        return str(output_path)

    monkeypatch.setattr(
        OpenAIImageGenerationTool,
        "_generate_single_image",
        fake_generate_single_image,
    )

    tool = OpenAIImageGenerationTool(
        output_directory=str(tmp_path),
        requests=[
            ImageGenerationRequest(prompt="default quality sample"),
            ImageGenerationRequest(
                prompt="high quality sample",
                quality="high",
            ),
        ],
    )

    asyncio.run(tool.run())

    assert observed_qualities == ["low", "high"]

