from inspect import Parameter, signature
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.main import app
from app.services.stt_service import OpenAISTTService, WhisperSTTService

LANGUAGE_CASES = [
    ("en-US", "en"),
    ("en-GB", "en"),
    ("de-DE", "de"),
    ("es-ES", "es"),
    ("fr-FR", "fr"),
    ("it-IT", "it"),
    ("ja-JP", "ja"),
    ("ko-KR", "ko"),
    ("pt-PT", "pt"),
    ("zh-CN", "zh"),
]


async def _make_plan(db_session, user_id: int, target_language: str):
    from tests.conftest import make_study_plan

    plan = await make_study_plan(
        db_session,
        user_id=user_id,
        target_language=target_language,
        cefr_level="A1",
        goals=["grammar"],
        duration_weeks=4,
        days_per_week=4,
        current_unit="",
        generated_plan={},
        is_active=True,
    )
    await db_session.commit()
    return plan


@pytest.fixture
def mock_stt_service():
    missing = object()
    previous_service = getattr(app.state, "stt_service", missing)
    service = SimpleNamespace(
        model="whisper-1",
        transcribe=AsyncMock(return_value="transcribed text"),
    )
    app.state.stt_service = service
    yield service
    if previous_service is missing:
        del app.state.stt_service
    else:
        app.state.stt_service = previous_service


@pytest.mark.parametrize(("target_language", "expected_language"), LANGUAGE_CASES)
@pytest.mark.asyncio
async def test_stt_uses_owned_study_plan_language(
    client,
    test_user,
    db_session,
    mock_stt_service,
    target_language,
    expected_language,
) -> None:
    user, headers = test_user
    plan = await _make_plan(db_session, user.id, target_language)

    response = await client.post(
        "/api/stt",
        headers=headers,
        data={"study_plan_id": str(plan.id)},
        files={"audio": ("recording.wav", b"audio-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "transcribed text"}
    mock_stt_service.transcribe.assert_awaited_once_with(
        b"audio-bytes",
        "recording.wav",
        mime_type="audio/wav",
        language=expected_language,
    )


@pytest.mark.asyncio
async def test_stt_requires_study_plan_id(
    client,
    test_user,
    mock_stt_service,
) -> None:
    _, headers = test_user

    response = await client.post(
        "/api/stt",
        headers=headers,
        files={"audio": ("recording.wav", b"audio-bytes", "audio/wav")},
    )

    assert response.status_code == 422
    mock_stt_service.transcribe.assert_not_awaited()


@pytest.mark.parametrize("study_plan_id", ["0", "2147483648", "not-a-number"])
@pytest.mark.asyncio
async def test_stt_rejects_invalid_study_plan_id(
    client,
    test_user,
    mock_stt_service,
    study_plan_id,
) -> None:
    _, headers = test_user

    response = await client.post(
        "/api/stt",
        headers=headers,
        data={"study_plan_id": study_plan_id},
        files={"audio": ("recording.wav", b"audio-bytes", "audio/wav")},
    )

    assert response.status_code == 422
    mock_stt_service.transcribe.assert_not_awaited()


@pytest.mark.asyncio
async def test_stt_rejects_study_plan_owned_by_another_user(
    client,
    test_user,
    admin_user,
    db_session,
    mock_stt_service,
) -> None:
    _, headers = test_user
    other_user, _ = admin_user
    other_plan = await _make_plan(db_session, other_user.id, "it-IT")

    response = await client.post(
        "/api/stt",
        headers=headers,
        data={"study_plan_id": str(other_plan.id)},
        files={"audio": ("recording.wav", b"audio-bytes", "audio/wav")},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Study plan not found"}
    mock_stt_service.transcribe.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_stt_forwards_required_language(monkeypatch) -> None:
    create = AsyncMock(return_value=SimpleNamespace(text=" Credo che abbiano poco tempo. "))
    client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=create),
        )
    )
    monkeypatch.setattr(
        "app.services.stt_service.openai.AsyncOpenAI",
        lambda api_key: client,
    )
    service = OpenAISTTService(api_key="test-key", model="whisper-1")

    text = await service.transcribe(
        b"wav-bytes",
        "recording.wav",
        "audio/wav",
        language="it",
    )

    assert text == "Credo che abbiano poco tempo."
    kwargs = create.await_args.kwargs
    assert kwargs["model"] == "whisper-1"
    assert kwargs["language"] == "it"
    assert kwargs["timeout"] == 60.0
    filename, audio_file, mime_type = kwargs["file"]
    assert filename == "recording.wav"
    assert audio_file.read() == b"wav-bytes"
    assert mime_type == "audio/wav"

    language_parameter = signature(OpenAISTTService.transcribe).parameters["language"]
    assert language_parameter.kind is Parameter.KEYWORD_ONLY
    assert language_parameter.default is Parameter.empty


@pytest.mark.asyncio
async def test_local_stt_forwards_required_language(monkeypatch) -> None:
    response = SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {"text": " Ich spreche Deutsch. "},
    )
    post = AsyncMock(return_value=response)

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(self, *args, **kwargs):
            return await post(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.stt_service.httpx.AsyncClient",
        FakeAsyncClient,
    )
    service = WhisperSTTService(base_url="http://whisper:9000")

    text = await service.transcribe(
        b"wav-bytes",
        "recording.wav",
        "audio/wav",
        language="de",
    )

    assert text == "Ich spreche Deutsch."
    post.assert_awaited_once_with(
        "http://whisper:9000/asr",
        params={"output": "json", "language": "de", "task": "transcribe"},
        files={"audio_file": ("recording.wav", b"wav-bytes", "audio/wav")},
        timeout=60.0,
    )
