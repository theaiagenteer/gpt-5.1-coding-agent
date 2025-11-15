from agency_swarm.tools import BaseTool
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pathlib import Path
import asyncio
import base64
import os


load_dotenv()


class ImageGenerationRequest(BaseModel):
    """
    A single image generation request.

    This separates the inputs into a dedicated type so that agents can pass an
    array of requests, each with its own prompt, optional filename, and size.
    """

    prompt: str = Field(
        ...,
        description="The natural language prompt describing the image to generate.",
    )
    filename: str | None = Field(
        None,
        description=(
            "Optional filename (relative to the tool's output directory) for the "
            "generated image. If omitted, the tool will generate sequential filenames "
            "like 'image-1.png'."
        ),
    )
    size: str = Field(
        "1024x1024",
        description=(
            "Requested image size for this generation. Common options for gpt-image-1 "
            "include '1024x1024', '1024x1536', and '1536x1024'."
        ),
    )
    quality: str = Field(
        "low",
        description=(
            "Image quality level for this request (e.g., 'low' or 'high'). Defaults to "
            "'low' to optimize for speed and cost."
        ),
    )


class OpenAIImageGenerationTool(BaseTool):
    """
    Generates one or more images using OpenAI's image generation API and saves them to disk.

    Always use absolute paths for the output directory.

    Keep quality low if generating more than 2-3 images. Increase quality if explicitly requested.
    """

    output_directory: str = Field(
        ...,
        description=(
            "Absolute directory path where all generated images will be stored. "
            "This directory is created if it does not exist."
        ),
    )
    requests: list[ImageGenerationRequest] = Field(
        ...,
        description=(
            "List of image generation requests. Each item contains a prompt, optional "
            "filename, size, and quality."
        ),
    )

    @field_validator("output_directory")
    @classmethod
    def _ensure_absolute_output_directory(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("output_directory must be an absolute path.")
        return str(path)

    async def run(self) -> str:
        """
        Generate images with OpenAI's images API and save them beneath the shared
        output directory.

        Steps for each request:
        1. Ensure the shared output directory exists.
        2. Build the target file path (respecting any custom filename).
        3. Call OpenAI's image generation endpoint with the given prompt and size.
        4. Decode the base64-encoded image returned by the API.
        5. Write the decoded bytes to disk.
        After processing all requests, return a summary message listing all saved paths.
        """
        # Step 1: Initialize async OpenAI client (reads OPENAI_API_KEY from environment)
        client = AsyncOpenAI()
        output_dir = Path(self.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 2: Fire off all image generation calls in parallel
        tasks = [
            self._generate_single_image(
                client,
                req,
                self._build_output_path(output_dir, index, req.filename),
                req.quality,
            )
            for index, req in enumerate(self.requests, start=1)
        ]
        saved_paths = await asyncio.gather(*tasks)

        return f"Generated {len(saved_paths)} image(s) and saved to: {', '.join(saved_paths)}"

    def _build_output_path(
        self, base_dir: Path, index: int, filename: str | None
    ) -> Path:
        """
        Build the final output path for a request while ensuring filenames stay within
        the shared output directory.
        """
        if filename:
            candidate = Path(filename)
            if candidate.is_absolute():
                raise ValueError(
                    "Request filenames must be relative; absolute paths are not allowed."
                )
            output_path = base_dir / candidate
        else:
            output_path = base_dir / f"image-{index}.png"

        return output_path

    async def _generate_single_image(
        self,
        client: AsyncOpenAI,
        req: ImageGenerationRequest,
        output_path: Path,
        quality: str,
    ) -> str:
        """
        Generate a single image for one request and return the final absolute path.
        """
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Call the images API for this request
        response = await client.images.generate(
            model="gpt-image-1",
            prompt=req.prompt,
            size=req.size,
            n=1,
            quality=quality,
        )

        # Decode the base64 image data
        image_b64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        # Write the image to disk
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        return str(output_path)


if __name__ == "__main__":
    """
    Basic manual test for the tool.

    This will attempt to generate two images and save them beneath 'mnt/test-images'
    if an OPENAI_API_KEY is configured. Any exceptions are printed so the script
    exits gracefully even in environments without network access.
    """
    api_key_present = bool(os.getenv("OPENAI_API_KEY"))

    if not api_key_present:
        print("OPENAI_API_KEY is not set; skipping live image generation test.")
    else:
        try:
            output_dir = Path("mnt/test-images").resolve()
            test_tool = OpenAIImageGenerationTool(
                output_directory=str(output_dir),
                requests=[
                    ImageGenerationRequest(
                        prompt="A minimalist flat illustration of a robot writing code at a desk.",
                        filename="test-1.png",
                        size="1024x1024",
                    ),
                    ImageGenerationRequest(
                        prompt="A futuristic city skyline at night in flat illustration style.",
                        filename="city/test-2.png",
                        size="1024x1536",
                        quality="high",
                    ),
                ]
            )
            result = asyncio.run(test_tool.run())
            print(result)
        except Exception as exc:
            print(f"Image generation test failed: {exc}")


