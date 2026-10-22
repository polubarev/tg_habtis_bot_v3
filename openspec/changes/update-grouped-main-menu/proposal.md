# Change: Group the main Telegram menu

## Why
The main reply keyboard has six rows and requires scrolling in the user's Telegram client. Group existing actions into a compact menu while keeping each action easy to find.

## What Changes
- Replace the main menu with two rows: `📓 Записи | 📊 Обзор` and `🧰 Инструменты | ⚙️ Настройки` (localized in English too).
- Records: Habits / Day and Dream in the first row, Thought and Reflection in the second, Back in the third.
- Review: Week Analysis and On this day in the first row, Back in the second.
- Tools: Transcription and Help in the first row, Back in the second.
- Keep the existing Settings submenu and its actions available.
- Back returns to the main menu. Cancel remains available in input flows and as a slash command; it is removed from the idle main menu.
- Register `/cancel` through the existing button cancellation path: inspection found that prompts mentioned this command but the bot had no command handler for it.
- Preserve existing slash commands and recognition of old action labels from keyboards already displayed in Telegram.
- Opening a category must not treat its label as entry content or silently discard an unfinished entry. Existing flow-specific controls take precedence; active input flows must be finished or cancelled before switching categories.

## Impact
- Affected specs: menu-navigation (new).
- Affected code: `src/config/constants.py`, `src/services/telegram/keyboards.py`, `src/services/telegram/handlers/router.py`, `src/services/telegram/bot.py`, menu and routing tests, user-facing menu documentation.
- No new external dependencies or storage changes are intended.
- Existing action behavior remains the same; reaching an action from the main menu requires one additional tap.

## Approval and validation
- Status: approved by the user on 2026-10-22; implemented locally, not deployed.
- Verification: 243 tests passed, 1 skipped; Ruff passed. Tests run outside the sandbox because Windows loopback socket restrictions prevent asyncio event-loop creation inside it.
- Type checking was attempted using mypy's Python sources because Windows Application Control blocks its compiled extensions. The default check reported missing third-party type information for `requests` and `google.cloud.firestore`. With `import-untyped` disabled, it reported existing unused `type: ignore` comments in the unchanged transcription and reminder schedulers. Neither run reported diagnostics in changed source files; a clean full type check remains unavailable in this environment.
- The OpenSpec CLI is not installed or available on PATH in this workspace, so strict CLI validation has not been run.
