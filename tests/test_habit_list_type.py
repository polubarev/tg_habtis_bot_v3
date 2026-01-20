from src.models.habit import HabitFieldConfig
from src.services.telegram.handlers.habits import _normalize_list_value
from src.services.telegram.handlers.habits_config import (
    _normalize_default_value,
    _normalize_list_options,
    _parse_default_text,
)


def test_normalize_list_options_dedupes_casefold():
    options = _normalize_list_options("home, Office, HOME, office, holiday")
    assert options == ["home", "Office", "holiday"]


def test_normalize_list_value_single_select_matches_canonical():
    options = ["Home", "Office", "Holiday"]
    assert _normalize_list_value("office", options, False) == "Office"


def test_normalize_list_value_multiple_select_preserves_option_order():
    options = ["Home", "Office", "Holiday"]
    value = ["holiday", "home"]
    assert _normalize_list_value(value, options, True) == ["Home", "Holiday"]


def test_parse_default_text_list_single():
    cfg = HabitFieldConfig(
        type="list",
        description="Work place",
        options=["Home", "Office", "Holiday"],
        allow_multiple=False,
    )
    parsed, error_key, _ = _parse_default_text("office", cfg)
    assert error_key is None
    assert parsed == "Office"


def test_parse_default_text_list_multiple():
    cfg = HabitFieldConfig(
        type="list",
        description="Work place",
        options=["Home", "Office", "Holiday"],
        allow_multiple=True,
    )
    parsed, error_key, _ = _parse_default_text("holiday, home", cfg)
    assert error_key is None
    assert parsed == ["Home", "Holiday"]


def test_normalize_default_value_list_multiple():
    cfg = HabitFieldConfig(
        type="list",
        description="Work place",
        options=["Home", "Office", "Holiday"],
        allow_multiple=True,
    )
    parsed, error_key, _ = _normalize_default_value(["office", "home"], cfg)
    assert error_key is None
    assert parsed == ["Home", "Office"]
