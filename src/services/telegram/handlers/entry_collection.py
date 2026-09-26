from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from datetime import date
import json

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.core.analytics import log_event
from src.models.enums import EntryType, InputType
from src.models.session import ConversationState, SessionData
from src.models.text_entry_collection import TextEntryCollectionStatus
from src.services.entry_collection import CollectionAction
from src.services.telegram.keyboards import (
    build_confirmation_keyboard,
    build_entry_collection_keyboard,
)
from src.services.telegram.utils import (
    get_entry_collection_manager,
    get_session_repo,
    get_settings_from_context,
    resolve_language,
    resolve_user_profile,
    reply_confirmation_preview,
    reply_text_chunked,
    safe_delete_message,
)


def _messages(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _status_text(collection, lang: str, *, intro: str | None = None) -> str:
    settings_limit = collection.context.get("max_units")
    limit = settings_limit or 30_000
    status = _messages(lang)["entry_collect_status"].format(
        count=len(collection.parts),
        length=collection.total_utf16_units,
        limit=limit,
    )
    return f"{intro}\n\n{status}" if intro else status


async def start_entry_collection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    entry_type: EntryType,
    *,
    flow_context: dict[str, Any] | None = None,
    intro: str | None = None,
) -> None:
    if not update.effective_user or not update.effective_chat:
        return
    manager = get_entry_collection_manager(context)
    session_repo = get_session_repo(context)
    if manager is None or session_repo is None:
        return
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    collection_context = dict(flow_context or {})
    collection_context["max_units"] = get_settings_from_context(
        context
    ).text_entry_max_utf16_units
    collection = await manager.start(
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
        entry_type=entry_type,
        context=collection_context,
    )
    log_event(
        "entry_collection.started",
        user_id=update.effective_user.id,
        entry_type=entry_type.value,
    )
    session = await session_repo.get(update.effective_user.id) or SessionData(
        user_id=update.effective_user.id
    )
    session.state = ConversationState.ENTRY_COLLECTING
    session.pending_entry = None
    await session_repo.save(session)

    text = _status_text(
        collection,
        lang,
        intro=intro or _messages(lang)["entry_collect_intro"],
    )
    keyboard = build_entry_collection_keyboard(lang)
    sent = None
    if update.callback_query:
        sent = await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=keyboard
        )
    elif update.message:
        sent = await update.message.reply_text(text, reply_markup=keyboard)
    sent_message_id = getattr(sent, "message_id", None)
    if sent_message_id is not None:
        await manager.set_status_message(
            user_id=update.effective_user.id,
            collection_id=collection.collection_id,
            message_id=sent_message_id,
        )
        if update.callback_query:
            await safe_delete_message(cast(Any, update.callback_query.message))


async def _refresh_status(context, collection, lang: str, message) -> None:
    text = _status_text(collection, lang)
    keyboard = build_entry_collection_keyboard(lang)
    previous_status_id = collection.status_message_id
    # Editing a message leaves it above newly received parts in the chat.
    sent = await message.reply_text(text, reply_markup=keyboard)
    manager = get_entry_collection_manager(context)
    if manager is not None and getattr(sent, "message_id", None) is not None:
        await manager.set_status_message(
            user_id=collection.user_id,
            collection_id=collection.collection_id,
            message_id=sent.message_id,
        )
    if previous_status_id:
        try:
            await context.bot.delete_message(
                chat_id=collection.chat_id,
                message_id=previous_status_id,
            )
        except Exception:
            # Keep the new card usable even if Telegram cannot remove the old one.
            pass


async def handle_entry_collection_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    *,
    input_type: InputType = InputType.TEXT,
) -> bool:
    if not update.effective_user or not update.message:
        return False
    session_repo = get_session_repo(context)
    manager = get_entry_collection_manager(context)
    if session_repo is None or manager is None:
        return False
    session = await session_repo.get(update.effective_user.id)
    if session is None or session.state != ConversationState.ENTRY_COLLECTING:
        return False
    collection = await manager.get(update.effective_user.id)
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    if collection is None:
        session.reset()
        await session_repo.save(session)
        await update.message.reply_text(_messages(lang)["session_expired"])
        return True
    outcome = await manager.add_part(
        user_id=update.effective_user.id,
        collection_id=collection.collection_id,
        message_id=update.message.message_id,
        text=text,
        input_type=input_type,
    )
    log_event(
        "entry_collection.part",
        user_id=update.effective_user.id,
        entry_type=outcome.collection.entry_type.value,
        source=input_type.value,
        accepted=outcome.code == "accepted",
        reason=None if outcome.code == "accepted" else outcome.code,
        part_count=len(outcome.collection.parts),
        total_utf16_units=outcome.collection.total_utf16_units,
    )
    if outcome.code == "too_large":
        await update.message.reply_text(
            _messages(lang)["entry_collect_too_large"].format(
                limit=get_settings_from_context(context).text_entry_max_utf16_units
            )
        )
    elif outcome.code == "not_collecting":
        await update.message.reply_text(_messages(lang)["entry_collect_processing"])
    await _refresh_status(context, outcome.collection, lang, update.message)
    return True


async def _process_collection(update: Any, context, collection) -> bool:
    session_repo = get_session_repo(context)
    if session_repo is None:
        return False
    session = await session_repo.get(collection.user_id) or SessionData(user_id=collection.user_id)
    if collection.entry_type == EntryType.HABIT and collection.context.get("selected_date"):
        session.selected_date = date.fromisoformat(collection.context["selected_date"])
        session.temp_data = session.temp_data or {}
        if collection.context.get("existing_entry_action"):
            session.temp_data["existing_entry_action"] = collection.context[
                "existing_entry_action"
            ]
    if collection.entry_type == EntryType.REFLECTION and collection.context.get("questions"):
        session.temp_data = session.temp_data or {}
        session.temp_data["reflect_questions"] = collection.context["questions"]

    handler_update = cast(
        Update,
        SimpleNamespace(
        effective_user=update.effective_user,
        effective_chat=update.effective_chat,
        message=cast(Any, update.callback_query).message,
        callback_query=None,
        entry_collection_processing=True,
        ),
    )
    if collection.entry_type == EntryType.HABIT:
        from src.services.telegram.handlers.habits import handle_habits_text

        session.state = ConversationState.HABITS_AWAITING_CONTENT
        await session_repo.save(session)
        await handle_habits_text(
            handler_update,
            context,
            collection.combined_text,
            input_type=collection.combined_input_type,
        )
        expected = ConversationState.HABITS_AWAITING_CONFIRMATION
    elif collection.entry_type == EntryType.DREAM:
        from src.services.telegram.handlers.dream import handle_dream_text

        session.state = ConversationState.DREAM_AWAITING_CONTENT
        await session_repo.save(session)
        await handle_dream_text(handler_update, context, collection.combined_text)
        expected = ConversationState.DREAM_AWAITING_CONFIRMATION
    elif collection.entry_type == EntryType.THOUGHT:
        from src.services.telegram.handlers.thought import handle_thought_text

        session.state = ConversationState.THOUGHT_AWAITING_CONTENT
        await session_repo.save(session)
        await handle_thought_text(handler_update, context, collection.combined_text)
        expected = ConversationState.THOUGHT_AWAITING_CONFIRMATION
    else:
        from src.services.telegram.handlers.reflect import handle_reflect_text

        session.state = ConversationState.REFLECT_ANSWERING_QUESTIONS
        await session_repo.save(session)
        await handle_reflect_text(handler_update, context, collection.combined_text)
        expected = ConversationState.REFLECT_AWAITING_CONFIRMATION

    updated = await session_repo.get(collection.user_id)
    return bool(updated and updated.state == expected and updated.pending_entry)


async def _retry_pending_preview(update: Any, context, collection, lang: str) -> bool:
    session_repo = get_session_repo(context)
    if session_repo is None:
        return False
    session = await session_repo.get(collection.user_id)
    if session is None or not session.pending_entry:
        return False
    message = cast(Any, update.callback_query).message
    pending = session.pending_entry
    if session.state == ConversationState.HABITS_AWAITING_CONFIRMATION:
        from src.services.telegram.handlers.habits import _format_habit_preview

        profile = await resolve_user_profile(update, context)
        preview = _format_habit_preview(
            pending,
            profile.habit_schema if profile else None,
            lang,
        )
        await reply_text_chunked(
            message,
            _messages(lang)["confirm_entry"] + "\n\n" + preview,
            reply_markup=build_confirmation_keyboard("habits", lang),
            parse_mode=ParseMode.HTML,
        )
        return True
    prefixes = {
        ConversationState.DREAM_AWAITING_CONFIRMATION: "dream",
        ConversationState.THOUGHT_AWAITING_CONFIRMATION: "thought",
        ConversationState.REFLECT_AWAITING_CONFIRMATION: "reflect",
    }
    prefix = prefixes.get(session.state)
    if prefix is None:
        return False
    preview = json.dumps(
        {key: value for key, value in pending.items() if key != "entry_id"},
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    await reply_confirmation_preview(
        message,
        _messages(lang)["confirm_generic"],
        preview,
        reply_markup=build_confirmation_keyboard(prefix, lang),
    )
    return True


async def handle_entry_collection_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.callback_query or not update.effective_user or not update.effective_chat:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("entry_collect:"):
        return
    action_name = data.split(":", 1)[1]
    manager = get_entry_collection_manager(context)
    session_repo = get_session_repo(context)
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    if manager is None or session_repo is None:
        await query.answer()
        return
    collection = await manager.get(update.effective_user.id)
    if collection is None:
        await query.answer()
        await query.edit_message_text(_messages(lang)["session_expired"])
        return

    if action_name == "edit":
        await query.answer()
        await start_entry_collection(
            update,
            context,
            collection.entry_type,
            flow_context=collection.context,
        )
        return
    if action_name == "cancel":
        await manager.apply_action(
            user_id=collection.user_id,
            collection_id=collection.collection_id,
            action=CollectionAction.CANCEL,
        )
        await manager.discard(collection.user_id)
        session = await session_repo.get(collection.user_id)
        if session:
            session.reset()
            await session_repo.save(session)
        log_event(
            "entry_collection.cancelled",
            user_id=collection.user_id,
            entry_type=collection.entry_type.value,
            part_count=len(collection.parts),
        )
        await query.answer()
        await query.edit_message_text(_messages(lang)["cancelled"])
        return
    if action_name == "undo":
        outcome = await manager.apply_action(
            user_id=collection.user_id,
            collection_id=collection.collection_id,
            action=CollectionAction.UNDO,
        )
        await query.answer(
            _messages(lang)["entry_collect_undo_empty"] if outcome.code == "empty" else None
        )
        await query.edit_message_text(
            _status_text(outcome.collection, lang),
            reply_markup=build_entry_collection_keyboard(lang),
        )
        log_event(
            "entry_collection.undo",
            user_id=collection.user_id,
            entry_type=collection.entry_type.value,
            part_count=len(outcome.collection.parts),
        )
        return

    if action_name not in {"done", "retry"}:
        await query.answer()
        return
    if action_name == "retry":
        try:
            if await _retry_pending_preview(update, context, collection, lang):
                await manager.mark_status(
                    user_id=collection.user_id,
                    collection_id=collection.collection_id,
                    status=TextEntryCollectionStatus.READY,
                )
                await safe_delete_message(cast(Any, query.message))
                await query.answer()
                return
        except Exception:
            pass
    outcome = await manager.apply_action(
        user_id=collection.user_id,
        collection_id=collection.collection_id,
        action=CollectionAction.DONE,
    )
    if outcome.code == "empty":
        await query.answer(_messages(lang)["entry_collect_empty"])
        return
    if outcome.code != "claimed":
        await query.answer(_messages(lang)["entry_collect_processing"])
        return
    await query.answer()
    await query.edit_message_text(_messages(lang)["entry_collect_processing"])
    try:
        ready = await _process_collection(update, context, outcome.collection)
        if not ready:
            raise RuntimeError("entry processing did not produce a pending confirmation")
        await manager.mark_status(
            user_id=collection.user_id,
            collection_id=collection.collection_id,
            status=TextEntryCollectionStatus.READY,
        )
        log_event(
            "entry_collection.completed",
            user_id=collection.user_id,
            entry_type=collection.entry_type.value,
            part_count=len(collection.parts),
            total_utf16_units=collection.total_utf16_units,
        )
        await safe_delete_message(cast(Any, query.message))
    except Exception:
        await manager.mark_status(
            user_id=collection.user_id,
            collection_id=collection.collection_id,
            status=TextEntryCollectionStatus.FAILED,
        )
        await query.edit_message_text(
            _messages(lang)["entry_collect_failed"],
            reply_markup=build_entry_collection_keyboard(lang, failed=True),
        )
        log_event(
            "entry_collection.failed",
            user_id=collection.user_id,
            entry_type=collection.entry_type.value,
            part_count=len(collection.parts),
        )
