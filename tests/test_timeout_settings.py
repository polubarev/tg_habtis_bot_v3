from src.config.settings import Settings


def test_stage_timeout_defaults_are_independent():
    settings = Settings(_env_file=None)

    assert settings.telegram_download_timeout_seconds == 30
    assert settings.transcription_timeout_seconds == 60
    assert settings.llm_timeout_seconds == 45
    assert settings.sheets_timeout_seconds == 25


def test_legacy_operation_timeout_is_a_fallback():
    settings = Settings(_env_file=None, operation_timeout_seconds=12)

    assert settings.telegram_download_timeout_seconds == 12
    assert settings.transcription_timeout_seconds == 12
    assert settings.llm_timeout_seconds == 12
    assert settings.sheets_timeout_seconds == 12


def test_stage_timeout_override_wins_over_legacy_fallback():
    settings = Settings(
        _env_file=None,
        operation_timeout_seconds=12,
        transcription_timeout_seconds=50,
    )

    assert settings.transcription_timeout_seconds == 50
    assert settings.llm_timeout_seconds == 12
