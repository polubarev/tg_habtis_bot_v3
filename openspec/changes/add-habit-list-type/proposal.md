# Change: Add list habit type with single/multi selection

## Why
Users want to track categorical habits (e.g., work_place = home/office/holiday) and have the LLM choose from a fixed list instead of free text.

## What Changes
- Add a new habit field type `list` with allowed `options` and a single vs multiple selection mode.
- Extend habit field configuration flow to collect list mode and comma-separated options.
- Extend JSON habit config import to accept list options and selection mode.
- Enforce list options during extraction and preview (unknown values become null).

## Impact
- Affected specs: habit-schema (new delta)
- Affected code: src/models/habit.py, src/services/telegram/handlers/habits_config.py, src/services/telegram/keyboards.py, src/config/constants.py, src/services/llm/extractors/habit_extractor.py, src/services/telegram/handlers/habits.py
