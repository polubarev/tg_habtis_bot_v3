from src.models.habit import HabitFieldConfig, HabitSchema

DEFAULT_REFLECTION_QUESTIONS_RU = [
    {"id": "gratitude", "text": "За что ты благодарен сегодня?"},
    {"id": "focus", "text": "Что было главным фокусом дня?"},
]

DEFAULT_REFLECTION_QUESTIONS_EN = [
    {"id": "gratitude", "text": "What are you grateful for today?"},
    {"id": "focus", "text": "What was your main focus today?"},
]

# Default habit schema for new users
DEFAULT_HABIT_SCHEMA = HabitSchema(
    fields={
        "diary": HabitFieldConfig(
            type="string",
            description=(
                "Ensure the diary matches the input description fully, "
                "only fixing typos and punctuation, and keep the same language."
            ),
            required=False,
        ),
    },  # base fields (timestamp, date, raw_record) are always present
    version=1,
)

# Sheet column order
HABITS_SHEET_COLUMNS = [
    "timestamp",
    "date",
    "raw_record",
    "diary",
]

DREAMS_SHEET_COLUMNS = [
    "timestamp",
    "record",
]

THOUGHTS_SHEET_COLUMNS = [
    "timestamp",
    "record",
]

# Button labels
BUTTONS_RU = {
    "habits": "📝 Привычки / День",
    "dream": "😴 Сон",
    "thought": "💭 Мысль",
    "reflect": "🤔 Рефлексия",
    "week_analysis": "📊 Анализ недели",
    "config": "⚙️ Настройки",
    "help": "ℹ️ Помощь",
    "cancel": "❌ Отмена",
    "back": "⬅️ Назад",
    "sheet_config": "📊 Таблица",
    "habits_config": "📋 Поля привычек",
    "reflect_config": "❓ Вопросы",
    "timezone": "🌍 Часовой пояс",
    "language": "🌐 Язык",
    "reminders": "🔔 Напоминания",
    "feedback": "💬 Обратная связь",
    "reset": "🧹 Сбросить всё",
}

BUTTONS_EN = {
    "habits": "📝 Habits / Day",
    "dream": "😴 Dream",
    "thought": "💭 Thought",
    "reflect": "🤔 Reflection",
    "week_analysis": "📊 Week Analysis",
    "config": "⚙️ Config",
    "help": "ℹ️ Help",
    "cancel": "❌ Cancel",
    "back": "⬅️ Back",
    "sheet_config": "📊 Sheet",
    "habits_config": "📋 Habit Fields",
    "reflect_config": "❓ Questions",
    "timezone": "🌍 Timezone",
    "language": "🌐 Language",
    "reminders": "🔔 Reminders",
    "feedback": "💬 Feedback",
    "reset": "🧹 Reset",
}

INLINE_BUTTONS_RU = {
    "today": "Сегодня",
    "yesterday": "Вчера",
    "custom_date": "Другая дата",
    "cancel": "Отмена",
    "confirm_yes": "✅ Да",
    "confirm_no": "✖ Нет",
    "existing_append": "Дополнить",
    "existing_rewrite": "Перезаписать",
    "habit_add": "➕ Добавить",
    "habit_edit": "✏️ Изменить",
    "habit_remove": "➖ Удалить",
    "habit_json": "📦 JSON",
    "habit_reset": "↩️ Сбросить",
    "habit_cancel": "✖ Отмена",
    "habit_type_string": "string",
    "habit_type_int": "int",
    "habit_type_float": "float",
    "habit_type_bool": "bool",
    "habit_edit_name": "Название",
    "habit_edit_description": "Описание",
    "habit_edit_type": "Тип",
    "habit_edit_min": "Минимум",
    "habit_edit_max": "Максимум",
    "habit_edit_default": "По умолчанию",
    "question_add": "➕ Добавить",
    "question_remove": "➖ Удалить",
    "question_reset": "↩️ Сбросить",
    "question_cancel": "✖ Отмена",
    "language_en": "English",
    "language_ru": "Русский",
}

INLINE_BUTTONS_EN = {
    "today": "Today",
    "yesterday": "Yesterday",
    "custom_date": "Custom date",
    "cancel": "Cancel",
    "confirm_yes": "✅ Yes",
    "confirm_no": "✖ No",
    "existing_append": "Append",
    "existing_rewrite": "Rewrite",
    "habit_add": "➕ Add",
    "habit_edit": "✏️ Edit",
    "habit_remove": "➖ Remove",
    "habit_json": "📦 JSON",
    "habit_reset": "↩️ Reset",
    "habit_cancel": "✖ Cancel",
    "habit_type_string": "string",
    "habit_type_int": "int",
    "habit_type_float": "float",
    "habit_type_bool": "bool",
    "habit_edit_name": "Name",
    "habit_edit_description": "Description",
    "habit_edit_type": "Type",
    "habit_edit_min": "Min",
    "habit_edit_max": "Max",
    "habit_edit_default": "Default",
    "question_add": "➕ Add",
    "question_remove": "➖ Remove",
    "question_reset": "↩️ Reset",
    "question_cancel": "✖ Cancel",
    "language_en": "English",
    "language_ru": "Русский",
}

# Message templates (Russian)
MESSAGES_RU = {
    "welcome": (
        "Привет! Я помогу вести дневник и отслеживать привычки.\n\n"
        "Сначала подключи Google Sheet, чтобы я мог сохранять записи:\n"
        "1) Открой ⚙️ Настройки → 📊 Таблица и вставь ссылку или ID Sheet.\n"
        "2) Настрой поля привычек: ⚙️ Настройки → 📋 Поля привычек (добавь метрики, которые хочешь вести).\n"
        "3) Настрой вопросы для рефлексии: ⚙️ Настройки → ❓ Вопросы (я буду задавать их при Рефлексии).\n\n"
        "Что я умею:\n"
        "• Привычки — запись дня/привычек с датой\n"
        "• Сон — записать сон\n"
        "• Мысль — быстрая заметка\n"
        "• Рефлексия — ответить на вопросы\n"
        "• Напоминания — ежедневные напоминания (в Настройках)\n"
        "• Настройки — подключить Google Sheet и настроить поля\n\n"
        "Нажми кнопку ниже, чтобы начать."
    ),
    "sheet_reminder": "Сначала укажи Google Sheet через Настройки -> Таблица.",
    "habits_restart": "Я не помню дату. Начни заново.",
    "dream_restart": "Начни заново с кнопки Сон.",
    "thought_restart": "Начни заново с кнопки Мысль.",
    "reflect_restart": "Начни заново с кнопки Рефлексия.",
    "select_date": "За какую дату хочешь сделать запись?",
    "date_custom_prompt": "Введи дату в формате YYYY-MM-DD (или dd.mm.yyyy).",
    "date_parse_error": "Не понял дату. Используй YYYY-MM-DD или dd.mm.yyyy.",
    "habit_fields_hint": "Я буду искать такие поля:\n{fields}",
    "habit_fields_hint_empty": "Пока нет полей привычек. Просто опиши день.",
    "describe_day": "Опиши свой день для {date} текстом или голосом.",
    "habits_existing_prompt": "У тебя уже есть запись за {date}. Дополнить её или перезаписать?",
    "processing": "⏳ Обрабатываю...",
    "saving_data": "💾 Сохраняю данные...",
    "confirm_entry": "📝 Черновик\nПосмотри черновик ниже и подтверди.",
    "saved_success": "✅ Сохранено!",
    "cancelled": "✖ Отменено.",
    "habits_update_prompt": "✏️ Отправь правки или новый текст. Я пересоберу черновик с учётом предыдущего сообщения.",
    "week_analysis_title": "📊 Анализ недели",
    "week_analysis_not_enough": "Недостаточно данных за последние 7 завершённых дней. Есть {count} дней.",
    "confirm_generic": "Проверь и подтверди:\n```json\n{preview}\n```",
    "error_occurred": "⚠ Произошла ошибка. Попробуй ещё раз.",
    "sheet_not_configured": "⚠ Сначала подключи Google Sheet.",
    "ask_sheet": (
        "Отправь ссылку или ID Google Sheets, куда писать данные.\n"
        "Требуемый доступ: \"Общий доступ → Ограничен\" и дать редактора боту."
    ),
    "sheet_permission_error": (
        "⚠ Нет доступа на запись в таблицу. "
        "Включи \"Общий доступ → Ограничен\" и дай права редактора боту."
    ),
    "sheet_write_error": (
        "⚠ Не удалось записать в таблицу. Проверь доступ и попробуй ещё раз."
    ),
    "external_timeout_error": (
        "⚠ Сервис не ответил вовремя. Попробуй ещё раз через минуту."
    ),
    "external_response_error": (
        "⚠ Получен некорректный ответ от сервиса. Попробуй ещё раз."
    ),
    "voice_transcription_error": "⚠ Не удалось распознать голос. Отправь текст.",
    "sheet_saved": "✅ Гугл-таблица сохранена.",
    "sheet_base_url_notice": "Использую базовую ссылку: {url}",
    "config_cancelled": "Настройка отменена.",
    "language_prompt": "Выбери язык интерфейса.",
    "language_saved": "✅ Язык сохранён.",
    "empty_value": "нет",
    "dream_prompt": "Опиши свой сон текстом или голосом.",
    "dream_saved": "✅ Сон сохранён.",
    "thought_prompt": "Окей, напиши мысль или заметку (текст/голос).",
    "thought_saved": "✅ Мысль сохранена.",
    "no_reflection_questions": "Нет вопросов для размышлений. Добавь их в /config.",
    "reflect_intro": "Ответь на вопросы одним сообщением (текст или голос). Список вопросов:\n{questions}\n\nОтправь один ответ — я разберу его и заполню ответы.",
    "reflect_done": "✅ Ответы сохранены.",
    "reflect_seeded": "Добавил вопросы по умолчанию.",
    "llm_disabled": "Без сводки: модель не настроена.",
    "voice_disabled": "Голос пока недоступен (нет ключа для STT). Отправь текст.",
    "voice_transcribed": "Расшифровка голоса: {text}",
    "help": (
        "🤖 *Помощь*\n\n"
        "Я умею вести дневник и трекать привычки в Google Sheet.\n\n"
        "📎 *Основные команды*:\n"
        "• 📝 *Привычки* — спрошу дату, затем можно отправить сводку дня, голосом или текстом.\n"
        "• 😴 *Сон* — запишу сон (добавлю в таблицу).\n"
        "• 💭 *Мысль* — быстрая заметка, чтобы не забыть.\n"
        "• 🤔 *Рефлексия* — задам список вопросов (настраиваются).\n"
        "• 🔔 *Напоминания* — ежедневное напоминание (Настройки → 🔔 Напоминания).\n"
        "• ⚙️ *Настройки* — подключение таблицы и редактирование полей.\n\n"
        "Если бот «завис» или ведёт себя странно — нажми ❌ *Отмена*."
    ),
    "habit_config_intro": (
        "Текущие поля:\n{fields}\n\n"
        "Что сделать:\n"
        "• ➕ Добавить поле (короткие шаги)\n"
        "• ✏️ Изменить поле\n"
        "• ➖ Удалить поле\n"
        "• ↩️ Сбросить к стандартным\n"
        "• 📦 Добавить несколько сразу (JSON, для опытных)\n\n"
        "Примеры полей:\n"
        "• вода — число 0–20\n"
        "• настроение — текст\n"
        "• боль — число 0–10\n"
        "• витамины — да/нет\n"
        "• кофе — число 0.0–5.0\n\n"
        "Нажми кнопку ниже."
    ),
    "habit_add_name_prompt": (
        "⭐️ *Шаг 1: Название*\n"
        "Короткая метка: только буквы/цифры, без пробелов. Пример: *вода* или *настроение*.\n"
        "Если нужно добавить много полей — нажми 📦 JSON."
    ),
    "habit_add_name_invalid": "Название не подошло. Нужны буквы/цифры без пробелов. Пример: вода.",
    "habit_add_name_taken": "Такое название уже есть. Придумай другое, например вода2.",
    "habit_add_name_reserved": "Это служебное название. Выбери другое, например вода.",
    "habit_add_description_prompt": (
        "⭐️ *Шаг 2: Описание*\n"
        "Поясни, что это за поле. Пример: «Стаканы воды»."
    ),
    "habit_add_description_error": "Нужно короткое описание. Пример: «Стаканы воды».",
    "habit_add_type_prompt": (
        "⭐️ *Шаг 3: Тип значения*\n"
        "Выбери один вариант:\n"
        "• string — текст (например, настроение)\n"
        "• int — целое число (например, 3)\n"
        "• float — число с точкой (например, 2.5)\n"
        "• bool — да/нет (например, выпил витамины)\n\n"
        "Нажми кнопку ниже."
    ),
    "habit_add_type_error": "Не понял тип. Нажми кнопку или напиши: string, int, float или bool. Пример: int.",
    "habit_add_min_prompt_int": (
        "⭐️ *Шаг 4: Минимум (необязательно)*\n"
        "Введи минимальное целое число, например 0. Или '-' чтобы пропустить."
    ),
    "habit_add_min_prompt_float": (
        "⭐️ *Шаг 4: Минимум (необязательно)*\n"
        "Введи минимальное число, например 0.5. Или '-' чтобы пропустить."
    ),
    "habit_add_min_error": (
        "Не похоже на число. Введи число (например, 0 или 0.5) или '-' чтобы пропустить."
    ),
    "habit_add_max_prompt_int": (
        "⭐️ *Шаг 5: Максимум (необязательно)*\n"
        "Введи максимальное целое число, например 10. Или '-' чтобы пропустить."
    ),
    "habit_add_max_prompt_float": (
        "⭐️ *Шаг 5: Максимум (необязательно)*\n"
        "Введи максимальное число, например 10.5. Или '-' чтобы пропустить."
    ),
    "habit_add_max_error": (
        "Не похоже на число. Введи число (например, 10 или 10.5) или '-' чтобы пропустить."
    ),
    "habit_add_max_less_than_min": (
        "Максимум не может быть меньше минимума ({min}). Введи число >= {min} или '-' чтобы пропустить."
    ),
    "habit_json_prompt": (
        "Хочешь добавить несколько полей сразу? Можно отправить JSON (для опытных).\n"
        "Пример (можно копировать):\n"
        "```json\n"
        "[\n"
        "  {\n"
        '    "name": "вода",\n'
        '    "description": "Стаканы воды",\n'
        '    "type": "int",\n'
        '    "minimum": 0,\n'
        '    "maximum": 20,\n'
        '    "required": true\n'
        "  },\n"
        "  {\n"
        '    "name": "настроение",\n'
        '    "description": "Как ты себя чувствуешь",\n'
        '    "type": "string",\n'
        '    "required": true\n'
        "  }\n"
        "]\n"
        "```"
    ),
    "habit_json_error": (
        "Не получилось прочитать JSON. Проверь формат и попробуй ещё раз. "
        "Если это сложно — используй кнопку ➕ Добавить."
    ),
    "habit_json_result_added": "✅ Добавлены поля: {added}",
    "habit_json_result_skipped": "⚠️ Пропущены (уже есть или базовые): {skipped}",
    "habit_json_result_none": "Ничего не добавлено. Проверь JSON по примеру или используй ➕ Добавить.",
    "habit_remove_prompt": (
        "Текущие пользовательские поля:\n{fields}\n"
        "Нажми кнопку поля или напиши его название. Пример: вода."
    ),
    "habit_remove_error": "Не нашёл такое поле. Проверь название и попробуй ещё раз. Пример: вода.",
    "habit_edit_prompt": (
        "Выбери поле для редактирования или напиши его название. Пример: вода."
    ),
    "habit_edit_not_found": "Не нашёл такое поле. Проверь название и попробуй ещё раз.",
    "habit_edit_details": (
        "Текущие значения поля:\n"
        "• Название: *{name}*\n"
        "• Описание: {description}\n"
        "• Тип: {type}\n"
        "• Минимум: {minimum}\n"
        "• Максимум: {maximum}\n"
        "• По умолчанию: {default}"
    ),
    "habit_edit_attr_prompt": "Что изменить в поле *{name}*?",
    "habit_edit_name_prompt": "Введи новое название для поля *{name}*.",
    "habit_edit_name_invalid": "Название не подошло. Нужны буквы/цифры без пробелов. Пример: вода.",
    "habit_edit_name_taken": "Такое название уже есть. Придумай другое, например вода2.",
    "habit_edit_name_reserved": "Это служебное название. Выбери другое, например вода.",
    "habit_edit_description_prompt": "Введи новое описание для поля *{name}*.",
    "habit_edit_description_error": "Нужно короткое описание. Пример: «Стаканы воды».",
    "habit_edit_type_prompt": "Выбери новый тип для поля *{name}*.",
    "habit_edit_min_not_numeric": "Минимум и максимум доступны только для числовых типов. Сначала измени тип.",
    "habit_edit_min_prompt_int": "Введи новый минимум (целое число) или '-' чтобы очистить.",
    "habit_edit_min_prompt_float": "Введи новый минимум (число) или '-' чтобы очистить.",
    "habit_edit_max_prompt_int": "Введи новый максимум (целое число) или '-' чтобы очистить.",
    "habit_edit_max_prompt_float": "Введи новый максимум (число) или '-' чтобы очистить.",
    "habit_edit_min_error": "Не похоже на число. Введи число или '-' чтобы очистить.",
    "habit_edit_max_error": "Не похоже на число. Введи число или '-' чтобы очистить.",
    "habit_edit_max_less_than_min": "Максимум не может быть меньше минимума ({min}).",
    "habit_add_default_prompt_int": "Введи значение по умолчанию (целое число) или '-' чтобы пропустить.",
    "habit_add_default_prompt_float": "Введи значение по умолчанию (число) или '-' чтобы пропустить.",
    "habit_add_default_prompt_bool": "Введи значение по умолчанию (да/нет) или '-' чтобы пропустить.",
    "habit_add_default_prompt_string": "Введи значение по умолчанию или '-' чтобы пропустить.",
    "habit_edit_default_prompt_int": "Введи новое значение по умолчанию (целое число) или '-' чтобы очистить.",
    "habit_edit_default_prompt_float": "Введи новое значение по умолчанию (число) или '-' чтобы очистить.",
    "habit_edit_default_prompt_bool": "Введи новое значение по умолчанию (да/нет) или '-' чтобы очистить.",
    "habit_edit_default_prompt_string": "Введи новое значение по умолчанию или '-' чтобы очистить.",
    "habit_default_error_number": "Не похоже на число. Введи число или '-' чтобы пропустить.",
    "habit_default_error_bool": "Не похоже на да/нет. Введи да/нет или '-' чтобы пропустить.",
    "habit_default_error_range_min": "Значение должно быть не меньше {min}.",
    "habit_default_error_range_max": "Значение должно быть не больше {max}.",
    "habit_default_error_range_between": "Значение должно быть от {min} до {max}.",
    "habit_updated": "✅ Поле обновлено: {name}",
    "habit_added": "Поле добавлено: {name}",
    "habit_removed": "Поле удалено: {name}",
    "habit_reset": "Схема привычек сброшена к стандартной.",
    "question_intro": "Текущие вопросы:\n{questions}\nЧто сделать?",
    "question_add_id_prompt": (
        "⭐️ *Шаг 1: Название*\n"
        "Короткое имя без пробелов. Примеры: *благодарность*, *фокус*."
    ),
    "question_add_text_prompt": "⭐️ *Шаг 2: Текст*\nНапиши текст вопроса.",
    "question_add_lang_prompt": "⭐️ *Шаг 3: Язык*\nВыбери язык вопроса: *ru*/*en* (по умолчанию текущий).",
    "question_add_active_prompt": "⭐️ *Шаг 4: Активен?*\nОтветь *yes/no* (по умолчанию *yes*).",
    "question_add_json_example": (
        "Можно сразу отправить JSON, пример:\n"
        "```json\n"
        '{"id":"gratitude","text":"За что ты благодарен?","language":"ru","active":true}\n'
        "```"
    ),
    "question_remove_prompt": "Выбери вопрос ниже, который удалить.",
    "question_added": "Вопрос добавлен: {id}",
    "question_removed": "Вопрос удалён: {id}",
    "question_reset": "Вопросы сброшены к стандартным.",
    "cancelled_config": "Настройка отменена.",
    "timezone_prompt": "Текущий пояс: {tz}. Отправь новый (например, Europe/Moscow, Asia/Jerusalem) или нажми Отмена.",
    "timezone_saved": "✅ Часовой пояс сохранён: {tz}",
    "timezone_error": "⚠ Не могу найти такой пояс. Попробуй: Europe/London, UTC, Asia/Jerusalem.",
    "reminder_prompt": (
        "Текущее время напоминания: {time}\n"
        "Отправь время в формате HH:MM (например, 21:00).\n"
        "Чтобы отключить, отправь off или выкл."
    ),
    "reminder_saved": "✅ Напоминание установлено на {time}.",
    "reminder_disabled": "🔕 Напоминания отключены.",
    "reminder_invalid_time": "Не понял время. Используй формат HH:MM, например 21:00.",
    "reminder_schedule_error": "⚠️ Не удалось запланировать напоминание. Попробуй ещё раз позже.",
    "reminder_message": "⏰ Напоминание: заполни дневник и привычки.",
    "config_menu": "⚙️ Настройки",
    "feedback_prompt": "Напиши, что можно улучшить или что не работает. Я сохраню отзыв.",
    "feedback_saved": "✅ Спасибо! Отзыв сохранён.",
    "feedback_error": "⚠️ Не удалось сохранить отзыв (Firestore недоступен). Попробуй позже.",
    "main_menu": "Главное меню",
    "reset_prompt": (
        "⚠️ Сбросит все данные в боте: подключённую таблицу, поля привычек, вопросы, часовой пояс и сессию. "
        "Твои записи в Google Sheet не трогаю.\n\nПродолжить?"
    ),
    "reset_done": "✅ Готово. Всё очищено. Нажми /start, чтобы настроиться заново.",
    "reset_cancelled": "✖ Сброс отменён.",
}

# Message templates (English)
MESSAGES_EN = {
    "welcome": (
        "Hello! I help you keep a diary and track habits.\n\n"
        "Start by connecting your Google Sheet so I can save entries:\n"
        "1) Open ⚙️ Config → 📊 Sheet and paste the Sheet link or ID.\n"
        "2) Add your own habit fields: ⚙️ Config → 📋 Habit Fields (metrics you want to track).\n"
        "3) Add reflection questions: ⚙️ Config → ❓ Questions (I'll ask them when you tap Reflection).\n\n"
        "What I can do:\n"
        "• Habits — diary + habits with date selection\n"
        "• Dream — log a dream\n"
        "• Thought — quick note\n"
        "• Reflection — answer custom questions\n"
        "• Reminders — daily reminders (via Config)\n"
        "• Config — set Google Sheet and fields\n\n"
        "Tap a button below to start."
    ),
    "sheet_reminder": "Please set your Google Sheet via Config -> Sheet first.",
    "habits_restart": "I lost the selected date. Start again.",
    "dream_restart": "Start over with Dream button.",
    "thought_restart": "Start over with Thought button.",
    "reflect_restart": "Start over with Reflection button.",
    "select_date": "Which date do you want to record?",
    "date_custom_prompt": "Enter a date as YYYY-MM-DD (or dd.mm.yyyy).",
    "date_parse_error": "Couldn't parse the date. Use YYYY-MM-DD or dd.mm.yyyy.",
    "habit_fields_hint": "I'll look for these fields:\n{fields}",
    "habit_fields_hint_empty": "No habit fields yet. Just describe your day.",
    "describe_day": "Describe your day for {date} using text or voice.",
    "habits_existing_prompt": "You already have a record for {date}. Append to it or rewrite it?",
    "processing": "⏳ Processing...",
    "saving_data": "💾 Saving data...",
    "confirm_entry": "📝 Draft\nReview the draft below and confirm.",
    "saved_success": "✅ Saved!",
    "cancelled": "✖ Cancelled.",
    "habits_update_prompt": "✏️ Send corrections or a new message. I’ll rebuild the draft using the previous text as context.",
    "week_analysis_title": "📊 Week Analysis",
    "week_analysis_not_enough": "Not enough data for the last 7 completed days. Only {count} days found.",
    "confirm_generic": "Review and confirm:\n```json\n{preview}\n```",
    "error_occurred": "⚠ An error occurred. Please try again.",
    "sheet_not_configured": "⚠ Please configure Google Sheet first.",
    "ask_sheet": (
        "Send a Google Sheet link or ID to store your data.\n"
        "Required sharing: \"General access → Restricted\" and grant the bot Editor access."
    ),
    "sheet_permission_error": (
        "⚠ I can’t write to this sheet. "
        "Set \"General access → Restricted\" and grant the bot Editor access."
    ),
    "sheet_write_error": "⚠ Couldn't write to the sheet. Check access and try again.",
    "external_timeout_error": "⚠ The service timed out. Please try again in a minute.",
    "external_response_error": "⚠ The service returned an invalid response. Please try again.",
    "voice_transcription_error": "⚠ Couldn't transcribe the audio. Please send text.",
    "sheet_saved": "✅ Google Sheet saved.",
    "sheet_base_url_notice": "Using base link: {url}",
    "config_cancelled": "Setup cancelled.",
    "language_prompt": "Choose your language.",
    "language_saved": "✅ Language saved.",
    "empty_value": "none",
    "dream_prompt": "Describe your dream (text or voice).",
    "dream_saved": "✅ Dream saved.",
    "thought_prompt": "Share your thought or note (text/voice).",
    "thought_saved": "✅ Thought saved.",
    "no_reflection_questions": "No reflection questions yet. Add them in /config.",
    "reflect_intro": "Answer all questions in one message (text or voice). Questions:\n{questions}\n\nSend a single reply — I'll parse it into answers.",
    "reflect_done": "✅ Answers saved.",
    "reflect_seeded": "Added default questions.",
    "llm_disabled": "Summary disabled: LLM not configured.",
    "voice_disabled": "Voice not available (no STT key). Please send text.",
    "voice_transcribed": "Voice transcription: {text}",
    "help": (
        "🤖 *Help*\n\n"
        "I help track habits and diary entries in Google Sheets.\n\n"
        "📎 *Commands*:\n"
        "• 📝 *Habits* — log your day (I'll ask date). Text or voice.\n"
        "• 😴 *Dream* — log a dream.\n"
        "• 💭 *Thought* — quick note.\n"
        "• 🤔 *Reflection* — answer Q&A check-ins.\n"
        "• 🔔 *Reminders* — daily reminders (Config → 🔔 Reminders).\n"
        "• ⚙️ *Config* — setup Sheet and custom fields.\n\n"
        "If stuck — press ❌ *Cancel*."
    ),
    "habit_config_intro": (
        "Current fields:\n{fields}\n\n"
        "What do you want to do?\n"
        "• ➕ Add a field (simple steps)\n"
        "• ✏️ Edit a field\n"
        "• ➖ Remove a field\n"
        "• ↩️ Reset to defaults\n"
        "• 📦 Add many at once (JSON, advanced)\n\n"
        "Examples:\n"
        "• water — number 0–20\n"
        "• mood — text\n"
        "• pain — number 0–10\n"
        "• vitamins — yes/no\n"
        "• coffee — number 0.0–5.0\n\n"
        "Tap a button below."
    ),
    "habit_add_name_prompt": (
        "⭐️ *Step 1: Name*\n"
        "Short label, letters/numbers only, no spaces. Example: *water* or *mood*.\n"
        "To add many fields, tap 📦 JSON."
    ),
    "habit_add_name_invalid": "That name doesn't work. Use letters/numbers only, no spaces. Example: water.",
    "habit_add_name_taken": "That name is already used. Pick another, e.g., water2.",
    "habit_add_name_reserved": "That name is reserved. Pick another, e.g., water.",
    "habit_add_description_prompt": (
        "⭐️ *Step 2: Description*\n"
        "Tell me what this field means. Example: \"Glasses of water\"."
    ),
    "habit_add_description_error": "Please send a short description. Example: \"Glasses of water\".",
    "habit_add_type_prompt": (
        "⭐️ *Step 3: Type of value*\n"
        "Choose one:\n"
        "• string — text (e.g., mood)\n"
        "• int — whole number (e.g., 3)\n"
        "• float — decimal (e.g., 2.5)\n"
        "• bool — yes/no (e.g., took vitamins)\n\n"
        "Tap a button below."
    ),
    "habit_add_type_error": "I didn't understand the type. Use a button or send: string, int, float, or bool. Example: int.",
    "habit_add_min_prompt_int": (
        "⭐️ *Step 4: Minimum (optional)*\n"
        "Send the smallest whole number, e.g., 0. Or '-' to skip."
    ),
    "habit_add_min_prompt_float": (
        "⭐️ *Step 4: Minimum (optional)*\n"
        "Send the smallest number, e.g., 0.5. Or '-' to skip."
    ),
    "habit_add_min_error": "That doesn't look like a number. Send a number (e.g., 0 or 0.5) or '-' to skip.",
    "habit_add_max_prompt_int": (
        "⭐️ *Step 5: Maximum (optional)*\n"
        "Send the largest whole number, e.g., 10. Or '-' to skip."
    ),
    "habit_add_max_prompt_float": (
        "⭐️ *Step 5: Maximum (optional)*\n"
        "Send the largest number, e.g., 10.5. Or '-' to skip."
    ),
    "habit_add_max_error": "That doesn't look like a number. Send a number (e.g., 10 or 10.5) or '-' to skip.",
    "habit_add_max_less_than_min": (
        "Max can't be smaller than min ({min}). Send a number >= {min} or '-' to skip."
    ),
    "habit_json_prompt": (
        "Want to add many fields at once? You can send JSON (advanced).\n"
        "Example (you can copy):\n"
        "```json\n"
        "[\n"
        "  {\n"
        '    "name": "water",\n'
        '    "description": "Glasses of water",\n'
        '    "type": "int",\n'
        '    "minimum": 0,\n'
        '    "maximum": 20,\n'
        '    "required": true\n'
        "  },\n"
        "  {\n"
        '    "name": "mood",\n'
        '    "description": "How you feel",\n'
        '    "type": "string",\n'
        '    "required": true\n'
        "  }\n"
        "]\n"
        "```"
    ),
    "habit_json_error": (
        "Couldn't read that JSON. Please follow the example and try again. "
        "If it's too much, use ➕ Add."
    ),
    "habit_json_result_added": "✅ Added fields: {added}",
    "habit_json_result_skipped": "⚠️ Skipped (already exist or base): {skipped}",
    "habit_json_result_none": "No fields added. Check the JSON example or use ➕ Add.",
    "habit_remove_prompt": (
        "Current custom fields:\n{fields}\n"
        "Tap a field button or send its name. Example: water."
    ),
    "habit_remove_error": "I couldn't find that field. Check the name and try again. Example: water.",
    "habit_edit_prompt": "Choose a field to edit or send its name. Example: water.",
    "habit_edit_not_found": "I couldn't find that field. Check the name and try again.",
    "habit_edit_details": (
        "Current field details:\n"
        "• Name: *{name}*\n"
        "• Description: {description}\n"
        "• Type: {type}\n"
        "• Min: {minimum}\n"
        "• Max: {maximum}\n"
        "• Default: {default}"
    ),
    "habit_edit_attr_prompt": "What do you want to edit in *{name}*?",
    "habit_edit_name_prompt": "Send a new name for *{name}*.",
    "habit_edit_name_invalid": "That name doesn't work. Use letters/numbers only, no spaces. Example: water.",
    "habit_edit_name_taken": "That name is already used. Pick another, e.g., water2.",
    "habit_edit_name_reserved": "That name is reserved. Pick another, e.g., water.",
    "habit_edit_description_prompt": "Send a new description for *{name}*.",
    "habit_edit_description_error": "Please send a short description. Example: \"Glasses of water\".",
    "habit_edit_type_prompt": "Choose a new type for *{name}*.",
    "habit_edit_min_not_numeric": "Min/max only work for numeric types. Change the type first.",
    "habit_edit_min_prompt_int": "Send a new minimum (whole number) or '-' to clear.",
    "habit_edit_min_prompt_float": "Send a new minimum (number) or '-' to clear.",
    "habit_edit_max_prompt_int": "Send a new maximum (whole number) or '-' to clear.",
    "habit_edit_max_prompt_float": "Send a new maximum (number) or '-' to clear.",
    "habit_edit_min_error": "That doesn't look like a number. Send a number or '-' to clear.",
    "habit_edit_max_error": "That doesn't look like a number. Send a number or '-' to clear.",
    "habit_edit_max_less_than_min": "Max can't be smaller than min ({min}).",
    "habit_add_default_prompt_int": "Send a default value (whole number) or '-' to skip.",
    "habit_add_default_prompt_float": "Send a default value (number) or '-' to skip.",
    "habit_add_default_prompt_bool": "Send a default value (yes/no) or '-' to skip.",
    "habit_add_default_prompt_string": "Send a default value or '-' to skip.",
    "habit_edit_default_prompt_int": "Send a new default value (whole number) or '-' to clear.",
    "habit_edit_default_prompt_float": "Send a new default value (number) or '-' to clear.",
    "habit_edit_default_prompt_bool": "Send a new default value (yes/no) or '-' to clear.",
    "habit_edit_default_prompt_string": "Send a new default value or '-' to clear.",
    "habit_default_error_number": "That doesn't look like a number. Send a number or '-' to skip.",
    "habit_default_error_bool": "That doesn't look like yes/no. Send yes/no or '-' to skip.",
    "habit_default_error_range_min": "Value must be at least {min}.",
    "habit_default_error_range_max": "Value must be at most {max}.",
    "habit_default_error_range_between": "Value must be between {min} and {max}.",
    "habit_updated": "✅ Field updated: {name}",
    "habit_added": "Field added: {name}",
    "habit_removed": "Field removed: {name}",
    "habit_reset": "Habit schema reset to defaults.",
    "question_intro": "Current questions:\n{questions}\nWhat would you like to do?",
    "question_add_id_prompt": (
        "⭐️ *Step 1: Name*\n"
        "Short name, no spaces. Examples: *gratitude*, *focus*."
    ),
    "question_add_text_prompt": "⭐️ *Step 2: Text*\nSend the question text.",
    "question_add_lang_prompt": "⭐️ *Step 3: Language*\nChoose *en*/*ru* (defaults to your current language).",
    "question_add_active_prompt": "⭐️ *Step 4: Active?*\nReply *yes/no* (default *yes*).",
    "question_add_json_example": (
        "You can also send full JSON, e.g.\n"
        "```json\n"
        '{"id":"gratitude","text":"What are you grateful for?","language":"en","active":true}\n'
        "```"
    ),
    "question_remove_prompt": "Pick a question below to remove.",
    "question_added": "Question added: {id}",
    "question_removed": "Question removed: {id}",
    "question_reset": "Questions reset to defaults.",
    "cancelled_config": "Setup cancelled.",
    "timezone_prompt": "Current: {tz}. Send new timezone (e.g. Europe/London, Asia/Jerusalem) or Cancel.",
    "timezone_saved": "✅ Timezone saved: {tz}",
    "timezone_error": "⚠ Unknown timezone. Try: Europe/London, UTC, Asia/Jerusalem.",
    "reminder_prompt": (
        "Current reminder time: {time}\n"
        "Send time as HH:MM (e.g., 21:00).\n"
        "To disable, send off or disable."
    ),
    "reminder_saved": "✅ Reminder set for {time}.",
    "reminder_disabled": "🔕 Reminders disabled.",
    "reminder_invalid_time": "Couldn't parse time. Use HH:MM, e.g., 21:00.",
    "reminder_schedule_error": "⚠️ Couldn't schedule the reminder. Please try again later.",
    "reminder_message": "⏰ Reminder: log your day and habits.",
    "config_menu": "⚙️ Settings",
    "feedback_prompt": "Share what could be improved or what doesn’t work. I’ll save your feedback.",
    "feedback_saved": "✅ Thanks! Your feedback was saved.",
    "feedback_error": "⚠️ Couldn't save feedback (Firestore unavailable). Please try again later.",
    "main_menu": "Main Menu",
    "reset_prompt": (
        "⚠️ This will wipe your bot data: connected Sheet, habit fields, questions, timezone, and session. "
        "Your existing rows in Google Sheets stay untouched.\n\nProceed?"
    ),
    "reset_done": "✅ Reset complete. Use /start to set up again.",
    "reset_cancelled": "✖ Reset cancelled.",
}
