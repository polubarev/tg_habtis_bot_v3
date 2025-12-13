from src.models.habit import HabitFieldConfig, HabitSchema

DEFAULT_REFLECTION_QUESTIONS = [
    {"id": "gratitude", "text": "За что ты благодарен сегодня?"},
    {"id": "focus", "text": "Что было главным фокусом дня?"},
]

# Default habit schema for new users
DEFAULT_HABIT_SCHEMA = HabitSchema(
    fields={
        "diary": HabitFieldConfig(
            type="string",
            description="Brief diary summary in the same language as input.",
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
    "config": "⚙️ Настройки",
    "help": "ℹ️ Помощь",
    "cancel": "❌ Отмена",
    "back": "⬅️ Назад",
    "sheet_config": "📊 Таблица",
    "habits_config": "📋 Поля привычек",
    "reflect_config": "❓ Вопросы",
    "timezone": "🌍 Часовой пояс",
}

BUTTONS_EN = {
    "habits": "📝 Habits / Day",
    "dream": "😴 Dream",
    "thought": "💭 Thought",
    "reflect": "🤔 Reflection",
    "config": "⚙️ Config",
    "help": "ℹ️ Help",
    "cancel": "❌ Cancel",
    "back": "⬅️ Back",
    "sheet_config": "📊 Sheet",
    "habits_config": "📋 Habit Fields",
    "reflect_config": "❓ Questions",
    "timezone": "🌍 Timezone",
}

# Message templates (Russian)
MESSAGES_RU = {
    "welcome": (
        "Привет! Я помогу вести дневник и отслеживать привычки.\n\n"
        "Что я умею:\n"
        "• Привычки — запись дня/привычек с датой\n"
        "• Сон — записать сон\n"
        "• Мысль — быстрая заметка\n"
        "• Рефлексия — ответить на вопросы\n"
        "• Настройки — указать Google Sheet и настроить поля\n\n"
        "Нажми кнопку ниже, чтобы начать."
    ),
    "sheet_reminder": "Сначала укажи Google Sheet через Настройки -> Таблица.",
    "habits_restart": "Я не помню дату. Начни заново.",
    "dream_restart": "Начни заново с кнопки Сон.",
    "thought_restart": "Начни заново с кнопки Мысль.",
    "reflect_restart": "Начни заново с кнопки Рефлексия.",
    "select_date": "За какую дату хочешь сделать запись?",
    "describe_day": "Опиши свой день для {date} текстом или голосом.",
    "processing": "⏳ Обрабатываю...",
    "confirm_entry": "📝 *Черновик*\nПосмотри JSON ниже и подтверди.",
    "saved_success": "✅ Сохранено!",
    "cancelled": "✖ Отменено.",
    "habits_update_prompt": "✏️ Отправь правки или новый текст. Я пересоберу черновик с учётом предыдущего сообщения.",
    "confirm_generic": "Проверь и подтверди:\n```json\n{preview}\n```",
    "error_occurred": "⚠ Произошла ошибка. Попробуй ещё раз.",
    "sheet_not_configured": "⚠ Сначала подключи Google Sheet.",
    "ask_sheet": "Отправь ссылку или ID Google Sheets, куда писать данные.",
    "sheet_saved": "✅ Гугл-таблица сохранена.",
    "config_cancelled": "Настройка отменена.",
    "dream_prompt": "Опиши свой сон текстом или голосом.",
    "dream_saved": "✅ Сон сохранён.",
    "thought_prompt": "Окей, напиши мысль или заметку (текст/голос).",
    "thought_saved": "✅ Мысль сохранена.",
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
        "• ⚙️ *Настройки* — подключение таблицы и редактирование полей.\n\n"
        "Если бот «завис» или ведёт себя странно — нажми ❌ *Отмена*."
    ),
    "habit_config_intro": "Текущие поля привычек: {fields}\nЧто сделать?",
    "habit_add_name_prompt": "⭐️ *Шаг 1: Название*\nНапиши имя поля (желательно латиницей, без пробелов).",
    "habit_add_description_prompt": "⭐️ *Шаг 2: Описание*\nКоротко опиши поле.",
    "habit_add_type_prompt": "⭐️ *Шаг 3: Тип*\nВыбери: *string* / *int* / *float* / *bool* (по умолчанию *string*).",
    "habit_add_min_prompt": "⭐️ *Шаг 4: Минимум*\nМинимальное число? Напиши или '-' чтобы пропустить.",
    "habit_add_max_prompt": "⭐️ *Шаг 5: Максимум*\nМаксимальное число? Напиши или '-' чтобы пропустить.",
    "habit_add_json_example": (
        "Можно сразу отправить JSON (один объект или список). Примеры:\n"
        "```json\n"
        '['
        '{"name":"water","description":"Стаканы воды","type":"int","minimum":0,"maximum":20,"required":true},'
        '{"name":"weight","description":"Вес в кг","type":"number","minimum":0,"maximum":400,"required":true},'
        '{"name":"mood","description":"Как ты себя чувствуешь","type":"string","required":true},'
        '{"name":"fasted","description":"Была ли голодовка","type":"boolean","required":false},'
        '{"name":"pain","description":"Уровень боли 0-10 (опционально)","type":["integer","null"],"minimum":0,"maximum":10,"required":false}'
        ']'
        "\n```"
    ),
    "habit_remove_prompt": "Отправь имя поля, которое удалить.",
    "habit_added": "Поле добавлено: {name}",
    "habit_removed": "Поле удалено: {name}",
    "habit_reset": "Схема привычек сброшена к стандартной.",
    "question_intro": "Текущие вопросы: {questions}\nЧто сделать?",
    "question_add_id_prompt": "⭐️ *Шаг 1: ID*\nУкажи id вопроса (латиницей, без пробелов).",
    "question_add_text_prompt": "⭐️ *Шаг 2: Текст*\nНапиши текст вопроса.",
    "question_add_lang_prompt": "⭐️ *Шаг 3: Язык*\nВыбери язык вопроса: *ru*/*en* (по умолчанию текущий).",
    "question_add_active_prompt": "⭐️ *Шаг 4: Активен?*\nОтветь *yes/no* (по умолчанию *yes*).",
    "question_add_json_example": (
        "Можно сразу отправить JSON, пример:\n"
        "```json\n"
        '{"id":"gratitude","text":"За что ты благодарен?","language":"ru","active":true}\n'
        "```"
    ),
    "question_remove_prompt": "Отправь id вопроса, который удалить.",
    "question_added": "Вопрос добавлен: {id}",
    "question_removed": "Вопрос удалён: {id}",
    "question_reset": "Вопросы сброшены к стандартным.",
    "cancelled_config": "Настройка отменена.",
    "timezone_prompt": "Текущий пояс: {tz}. Отправь новый (например, Europe/Moscow, Asia/Jerusalem) или нажми Отмена.",
    "timezone_saved": "✅ Часовой пояс сохранён: {tz}",
    "timezone_error": "⚠ Не могу найти такой пояс. Попробуй: Europe/London, UTC, Asia/Jerusalem.",
    "config_menu": "⚙️ Настройки",
    "main_menu": "Главное меню",
}

# Message templates (English)
MESSAGES_EN = {
    "welcome": (
        "Hello! I help you keep a diary and track habits.\n\n"
        "What I can do:\n"
        "• Habits — diary + habits with date selection\n"
        "• Dream — log a dream\n"
        "• Thought — quick note\n"
        "• Reflection — answer custom questions\n"
        "• Config — set Google Sheet and fields\n\n"
        "Tap a button below to start."
    ),
    "sheet_reminder": "Please set your Google Sheet via Config -> Sheet first.",
    "habits_restart": "I lost the selected date. Start again.",
    "dream_restart": "Start over with Dream button.",
    "thought_restart": "Start over with Thought button.",
    "reflect_restart": "Start over with Reflection button.",
    "select_date": "Which date do you want to record?",
    "describe_day": "Describe your day for {date} using text or voice.",
    "processing": "⏳ Processing...",
    "confirm_entry": "📝 *Draft*\nReview the JSON below and confirm.",
    "saved_success": "✅ Saved!",
    "cancelled": "✖ Cancelled.",
    "habits_update_prompt": "✏️ Send corrections or a new message. I’ll rebuild the draft using the previous text as context.",
    "confirm_generic": "Review and confirm:\n```json\n{preview}\n```",
    "error_occurred": "⚠ An error occurred. Please try again.",
    "sheet_not_configured": "⚠ Please configure Google Sheet first.",
    "ask_sheet": "Send a Google Sheet link or ID to store your data.",
    "sheet_saved": "✅ Google Sheet saved.",
    "config_cancelled": "Setup cancelled.",
    "dream_prompt": "Describe your dream (text or voice).",
    "dream_saved": "✅ Dream saved.",
    "thought_prompt": "Share your thought or note (text/voice).",
    "thought_saved": "✅ Thought saved.",
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
        "• ⚙️ *Config* — setup Sheet and custom fields.\n\n"
        "If stuck — press ❌ *Cancel*."
    ),
    "habit_config_intro": "Current habit fields: {fields}\nWhat would you like to do?",
    "habit_add_name_prompt": "⭐️ *Step 1: Name*\nPick a field id (letters/numbers, preferably no spaces).",
    "habit_add_description_prompt": "⭐️ *Step 2: Description*\nAdd a short description for this field.",
    "habit_add_type_prompt": "⭐️ *Step 3: Type*\nChoose: *string* / *int* / *float* / *bool* (defaults to *string*).",
    "habit_add_min_prompt": "⭐️ *Step 4: Minimum*\nMin number? Send a value or '-' to skip.",
    "habit_add_max_prompt": "⭐️ *Step 5: Maximum*\nMax number? Send a value or '-' to skip.",
    "habit_add_json_example": (
        "You can also send full JSON (single object or list). Examples:\n"
        "```json\n"
        '['
        '{"name":"water","description":"Glasses of water","type":"int","minimum":0,"maximum":20,"required":true},'
        '{"name":"weight","description":"Weight in kg","type":"number","minimum":0,"maximum":400,"required":true},'
        '{"name":"mood","description":"How you feel","type":"string","required":true},'
        '{"name":"fasted","description":"Fasted today","type":"boolean","required":false},'
        '{"name":"pain","description":"Pain level 0-10 (optional)","type":["integer","null"],"minimum":0,"maximum":10,"required":false}'
        ']'
        "\n```"
    ),
    "habit_remove_prompt": "Send the field name to remove.",
    "habit_added": "Field added: {name}",
    "habit_removed": "Field removed: {name}",
    "habit_reset": "Habit schema reset to defaults.",
    "question_intro": "Current questions: {questions}\nWhat would you like to do?",
    "question_add_id_prompt": "⭐️ *Step 1: ID*\nSet a question id (letters/numbers, no spaces).",
    "question_add_text_prompt": "⭐️ *Step 2: Text*\nSend the question text.",
    "question_add_lang_prompt": "⭐️ *Step 3: Language*\nChoose *en*/*ru* (defaults to your current language).",
    "question_add_active_prompt": "⭐️ *Step 4: Active?*\nReply *yes/no* (default *yes*).",
    "question_add_json_example": (
        "You can also send full JSON, e.g.\n"
        "```json\n"
        '{"id":"gratitude","text":"What are you grateful for?","language":"en","active":true}\n'
        "```"
    ),
    "question_remove_prompt": "Send the question id to remove.",
    "question_added": "Question added: {id}",
    "question_removed": "Question removed: {id}",
    "question_reset": "Questions reset to defaults.",
    "cancelled_config": "Setup cancelled.",
    "timezone_prompt": "Current: {tz}. Send new timezone (e.g. Europe/London, Asia/Jerusalem) or Cancel.",
    "timezone_saved": "✅ Timezone saved: {tz}",
    "timezone_error": "⚠ Unknown timezone. Try: Europe/London, UTC, Asia/Jerusalem.",
    "config_menu": "⚙️ Settings",
    "main_menu": "Main Menu",
}
