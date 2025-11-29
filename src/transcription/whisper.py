
from typing import Optional

import httpx


async def transcribe_audio(file_url: str, api_key: str) -> Optional[str]:
    """Send audio to Whisper API and return text transcription."""

    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(file_url, headers=headers)
        response.raise_for_status()
        # Placeholder: integrate with actual Whisper endpoint
        return response.text
