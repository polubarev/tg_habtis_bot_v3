from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.constants import BUTTONS_EN, BUTTONS_RU, MESSAGES_EN, MESSAGES_RU
from src.models.session import ConversationState, SessionData
from src.models.transcription_batch import TranscriptionBatchStatus
from src.models.user import UserProfile
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.storage.firestore.transcription_batch_repo import TranscriptionBatchRepository
from src.services.telegram.handlers import router
from src.services.telegram.keyboards import (
    build_config_keyboard,
    build_main_menu_keyboard,
    build_records_keyboard,
    build_review_keyboard,
    build_tools_keyboard,
)


@pytest.fixture(params=["ru", "en"])
def menu(request):
    language = request.param
    profile = UserProfile(telegram_user_id=1, language=language)
    sessions = SessionRepository(client=None)
    batches = TranscriptionBatchRepository()
    manager = SimpleNamespace(discard=AsyncMock())
    deps = SimpleNamespace(
        session_repo=lambda: sessions,
        user_repo=lambda: SimpleNamespace(get_by_telegram_id=AsyncMock(return_value=profile)),
        transcription_batch_repo=lambda: batches,
        entry_collection_manager=lambda: manager,
    )
    return SimpleNamespace(
        language=language,
        buttons=BUTTONS_RU if language == "ru" else BUTTONS_EN,
        messages=MESSAGES_RU if language == "ru" else MESSAGES_EN,
        sessions=sessions,
        batches=batches,
        manager=manager,
        context=SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps})),
    )


def _update(text):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=10),
        message=SimpleNamespace(text=text, reply_text=AsyncMock()),
    )


def _labels(keyboard):
    return [[button.text for button in row] for row in keyboard.keyboard]


def test_main_menu_has_only_four_categories(menu):
    buttons = menu.buttons
    assert _labels(build_main_menu_keyboard(menu.language)) == [
        [buttons["records"], buttons["review"]],
        [buttons["tools"], buttons["config"]],
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "builder", "actions"),
    [
        ("records", build_records_keyboard, ("habits", "dream", "thought", "reflect")),
        ("review", build_review_keyboard, ("week_analysis", "on_this_day")),
        ("tools", build_tools_keyboard, ("transcription", "help")),
        ("config", build_config_keyboard, ("sheet_config", "reminders", "reset")),
    ],
)
@pytest.mark.parametrize("label_language", ["ru", "en"])
async def test_open_category_and_return_to_main_menu(menu, category, builder, actions, label_language):
    labels = BUTTONS_RU if label_language == "ru" else BUTTONS_EN
    update = _update(labels[category])

    await router.route_text(update, menu.context)

    update.message.reply_text.assert_awaited_once_with(
        menu.messages[f"{category}_menu"], reply_markup=builder(menu.language)
    )
    keyboard = update.message.reply_text.call_args.kwargs["reply_markup"]
    displayed = [button.text for row in keyboard.keyboard for button in row]
    assert all(menu.buttons[action] in displayed for action in actions)
    assert menu.buttons["back"] in displayed
    if category != "config":
        assert len(keyboard.keyboard) <= 3

    back = _update(labels["back"])
    await router.route_text(back, menu.context)
    back.message.reply_text.assert_awaited_once_with(
        menu.messages["main_menu"], reply_markup=build_main_menu_keyboard(menu.language)
    )
    assert await menu.sessions.get(1) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["records", "review", "tools", "config"])
@pytest.mark.parametrize(
    "state",
    [
        ConversationState.HABITS_AWAITING_DATE,
        ConversationState.ENTRY_COLLECTING,
        ConversationState.THOUGHT_AWAITING_CONFIRMATION,
        ConversationState.CONFIG_TIMEZONE,
        ConversationState.TRANSCRIPTION_COLLECTING,
    ],
)
async def test_category_does_not_consume_or_reset_unfinished_input(menu, category, state):
    session = SessionData(
        user_id=1, state=state, pending_entry={"record": "Unfinished diary"}
    )
    await menu.sessions.save(session)
    before = session.model_dump()
    update = _update(menu.buttons[category])

    await router.route_text(update, menu.context)

    update.message.reply_text.assert_awaited_once_with(menu.messages["menu_finish_current"])
    assert (await menu.sessions.get(1)).model_dump() == before
    menu.manager.discard.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "handler"),
    [
        ("habits", "habits_command"),
        ("dream", "dream_command"),
        ("thought", "thought_command"),
        ("reflect", "reflect_command"),
        ("week_analysis", "week_analysis_command"),
        ("on_this_day", "on_this_day_command"),
        ("transcription", "transcription_command"),
        ("help", "help_command"),
    ],
)
@pytest.mark.parametrize("label_language", ["ru", "en"])
async def test_existing_action_labels_still_start_actions(
    menu, monkeypatch, action, handler, label_language
):
    command = AsyncMock()
    monkeypatch.setattr(router, handler, command)
    labels = BUTTONS_RU if label_language == "ru" else BUTTONS_EN
    update = _update(labels[action])

    await router.route_text(update, menu.context)

    command.assert_awaited_once_with(update, menu.context)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_command", [False, True])
async def test_cancel_discards_entry_and_returns_to_compact_main_menu(menu, use_command):
    await menu.sessions.save(
        SessionData(user_id=1, state=ConversationState.ENTRY_COLLECTING, pending_entry={"a": 1})
    )
    update = _update("/cancel" if use_command else menu.buttons["cancel"])

    if use_command:
        await router.cancel_command(update, menu.context)
    else:
        await router.route_text(update, menu.context)

    session = await menu.sessions.get(1)
    assert session.state == ConversationState.IDLE
    assert session.pending_entry is None
    menu.manager.discard.assert_awaited_once_with(1)
    update.message.reply_text.assert_awaited_once_with(
        menu.messages["cancelled"], reply_markup=build_main_menu_keyboard(menu.language)
    )


@pytest.mark.asyncio
async def test_category_preserves_transcription_batch_and_cancel_command_cancels_it(menu):
    batch = await menu.batches.create_or_resume(1, 10, 60)
    await menu.sessions.save(
        SessionData(
            user_id=1,
            state=ConversationState.TRANSCRIPTION_COLLECTING,
            temp_data={"transcription_batch_id": batch.batch_id},
        )
    )
    before = batch.model_dump()

    await router.route_text(_update(menu.buttons["records"]), menu.context)

    assert (await menu.batches.get(1)).model_dump() == before
    update = _update("/cancel")
    await router.cancel_command(update, menu.context)

    assert (await menu.batches.get(1)).status == TranscriptionBatchStatus.CANCELLED
    assert (await menu.sessions.get(1)).state == ConversationState.IDLE
    menu.manager.discard.assert_not_awaited()
    update.message.reply_text.assert_awaited_once_with(
        menu.messages["transcription_cancelled"],
        reply_markup=build_main_menu_keyboard(menu.language),
    )
