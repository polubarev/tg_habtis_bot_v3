from types import SimpleNamespace

import httpx
import pytest

from src.services.transcription import whisper


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "expected_hint"),
    [
        ("gpt-transcribe", 'name="languages[]"'),
        ("gpt-4o-transcribe", 'name="language"'),
    ],
)
async def test_transcription_request_and_language_response(monkeypatch, model, expected_hint):
    monkeypatch.setattr(
        whisper,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="test-key",
            whisper_model=model,
            transcription_timeout_seconds=60,
        ),
    )
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"text": "Привет", "languages": [{"code": "ru"}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        whisper.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )

    result = await whisper.WhisperClient().transcribe(
        b"sample audio", format="ogg", language_hint="ru"
    )

    assert result.text == "Привет"
    assert result.language == "ru"
    assert len(requests) == 1
    body = requests[0].read().decode("utf-8")
    assert 'name="model"' in body
    assert model in body
    assert expected_hint in body
    assert 'filename="audio.ogg"' in body