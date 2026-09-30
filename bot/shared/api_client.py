"""Shared async HTTP client for calling the newsletter2paper oneoff article endpoint."""

import httpx


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    async def convert_article(
        self,
        url: str,
        layout_type: str = "essay",
        remove_images: bool = False,
    ) -> dict:
        """POST /oneoff/article and return the JSON response."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{self.base_url}/oneoff/article",
                json={
                    "url": url,
                    "layout_type": layout_type,
                    "remove_images": remove_images,
                },
            )
            resp.raise_for_status()
            return resp.json()
