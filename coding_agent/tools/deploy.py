from agency_swarm.tools import BaseTool
from pydantic import Field
import os
import requests

UP2SHARE_ENDPOINT = "https://api.up2sha.re/v1/static-websites"


class DeployTool(BaseTool):
    """
    Uploads a static website ZIP file to up2sha.re using their Static Websites API.

    This tool mirrors the following curl command:

    curl -X POST \
      -H "X-Api-Key: <API_KEY>" \
      -F "file=@website.zip" \
      https://api.up2sha.re/v1/static-websites
    """

    zip_file_path: str = Field(
        ...,
        description="Absolute or relative path to the ZIP file containing the static website."
    )

    def run(self) -> str:
        api_key = "mCWrfqdiiGdQBagqWWecYif4oMBtroOr"
        if not api_key:
            raise EnvironmentError("UP2SHARE_API_KEY environment variable is not set.")

        if not os.path.isfile(self.zip_file_path):
            raise FileNotFoundError(f"File not found: {self.zip_file_path}")

        headers = {
            "X-Api-Key": api_key
        }

        with open(self.zip_file_path, "rb") as zip_file:
            files = {
                "file": zip_file
            }

            response = requests.post(
                UP2SHARE_ENDPOINT,
                headers=headers,
                files=files,
                timeout=60
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Upload failed ({response.status_code}): {response.text}"
            )

        return response.text

