from src.models.habit import HabitFieldConfig, HabitSchema

DEFAULT_REFLECTION_QUESTIONS = [
    {"id": "gratitude", "text": "За что ты благодарен сегодня?"},
    {"id": "focus", "text": "Что было главным фокусом дня?"},
]

# Default habit schema for new users
DEFAULT_HABIT_SCHEMA = HabitSchema(
    fields={
        "morning_exercises": HabitFieldConfig(
            type="integer",
            description="Whether the person did morning exercises. 0 = no, 1 = yes.",
            minimum=0,
            maximum=1,
        ),
        "training": HabitFieldConfig(
            type="integer",
            description="Whether the person did any training/workout. 0 = no, 1 = yes.",
            minimum=0,
            maximum=1,
        ),
        "alcohol": HabitFieldConfig(
            type="integer",
            description="Alcohol consumption level from 0 to 3.",
            minimum=0,
            maximum=3,
        ),
        "mood": HabitFieldConfig(
            type=["integer", "null"],
            description="Mood level 1-5 (1=very bad, 5=very good). null if not mentioned.",
            minimum=1,
            maximum=5,
            required=False,
        ),
        "sex": HabitFieldConfig(
            type="integer",
            description="Whether the person had sex. 0 = no, 1 = yes.",
            minimum=0,
            maximum=1,
        ),
        "masturbation": HabitFieldConfig(
            type="integer",
            description="Number of times the person masturbated.",
            minimum=0,
        ),
        "day_importance": HabitFieldConfig(
            type="integer",
            description="Day importance rating 1-3 (1=not important, 3=very important).",
            minimum=1,
            maximum=3,
        ),
        "diary": HabitFieldConfig(
            type="string",
            description="Brief LLM-generated summary of the day in the same language as input.",
            required=False,
        ),
        "raw_diary": HabitFieldConfig(
            type="string",
            description="Original user input or transcription. Never modified by LLM.",
        ),
    },
    version=1,
)

# Sheet column order
HABITS_SHEET_COLUMNS = [
    "date",
    "morning_exercises",
    "training",
    "alcohol",
    "mood",
    "sex",
    "masturbation",
    "day_importance",
    "raw_diary",
    "diary",
]

DREAMS_SHEET_COLUMNS = [
    "timestamp",
    "date",
    "raw_text",
]

THOUGHTS_SHEET_COLUMNS = [
    "timestamp",
    "raw_text",
]

# Message templates (Russian)
MESSAGES_RU = {
    "welcome": (
        "Привет! Я помогу вести дневник и отслеживать привычки.\n\n"
        "Что я умею:\n"
        "• /habits — запись дня/привычек с датой\n"
        "• /dream — записать сон\n"
        "• /thought — быстрая заметка\n"
        "• /reflect — ответить на вопросы\n"
        "• /config — указать Google Sheet\n"
        "• /habits_config — поля привычек\n"
        "• /questions — свои вопросы\n\n"
        "Нажми /habits (или кнопку ниже), выбери дату и опиши день текстом/голосом. Я покажу черновик и спрошу подтверждение."
    ),
    "sheet_reminder": "Сначала укажи Google Sheet через /config. Пример: https://docs.google.com/spreadsheets/d/1AbCDefGh1234567890",
    "habits_restart": "Я не помню дату. Нажми /habits и выбери дату заново.",
    "dream_restart": "Начни заново с /dream и опиши сон.",
    "thought_restart": "Начни заново с /thought и отправь заметку.",
    "reflect_restart": "Начни заново с /reflect, чтобы ответить на вопросы.",
    "select_date": "За какую дату хочешь сделать запись?",
    "describe_day": "Опиши свой день для {date} текстом или голосом.",
    "processing": "⏳ Обрабатываю...",
    "confirm_entry": "Проверь черновик:\nДата: {date}\nЧерновик: {raw}\nСводка: {diary}\n\nПодтвердить?",
    "saved_success": "✅ Сохранено!",
    "cancelled": "✖ Отменено.",
    "confirm_generic": "Проверь и подтверди:\n{preview}",
    "error_occurred": "⚠ Произошла ошибка. Попробуй ещё раз.",
    "sheet_not_configured": "⚠ Сначала подключи Google Sheet через /config.",
    "ask_sheet": "Отправь ссылку или ID Google Sheets, куда писать данные.",
    "sheet_saved": "✅ Гугл-таблица сохранена. Теперь можно писать /habits, /dream, /thought, /reflect.",
    "config_cancelled": "Настройка отменена.",
    "dream_prompt": "Опиши свой сон текстом или голосом.",
    "dream_saved": "✅ Сон сохранён.",
    "thought_prompt": "Окей, напиши мысль или заметку (текст/голос).",
    "thought_saved": "✅ Мысль сохранена.",
    "reflect_intro": "Отвечай на вопросы по одному. Напиши ответ:",
    "reflect_done": "✅ Ответы сохранены.",
    "reflect_seeded": "Добавил вопросы по умолчанию. Можно снова вызвать /reflect.",
    "llm_disabled": "Без сводки: модель не настроена.",
    "voice_disabled": "Голос пока недоступен (нет ключа для STT). Отправь текст.",
    "voice_transcribed": "Расшифровка голоса: {text}",
    "help": (
        "Команды:\n"
        "/start — приветствие и как работать\n"
        "/habits — запись привычек и дня\n"
        "/dream — записать сон\n"
        "/thought — быстрая мысль/заметка\n"
        "/reflect — ответы на свои вопросы\n"
        "/config — настроить Google Sheet\n"
        "/habits_config — поля привычек\n"
        "/questions — свои вопросы"
    ),
    "habit_config_intro": "Текущие поля привычек: {fields}\nЧто сделать?",
    "habit_add_prompt": "Отправь новое поле как: имя | описание | тип (string/int/bool, по умолчанию string).",
    "habit_remove_prompt": "Отправь имя поля, которое удалить.",
    "habit_added": "Поле добавлено: {name}",
    "habit_removed": "Поле удалено: {name}",
    "habit_reset": "Схема привычек сброшена к стандартной.",
    "question_intro": "Текущие вопросы: {questions}\nЧто сделать?",
    "question_add_prompt": "Отправь вопрос как: id | текст. id латиницей, без пробелов.",
    "question_remove_prompt": "Отправь id вопроса, который удалить.",
    "question_added": "Вопрос добавлен: {id}",
    "question_removed": "Вопрос удалён: {id}",
    "question_reset": "Вопросы сброшены к стандартным.",
    "cancelled_config": "Настройка отменена.",
}

# Message templates (English)
MESSAGES_EN = {
    "welcome": (
        "Hello! I help you keep a diary and track habits.\n\n"
        "What I can do:\n"
        "• /habits — diary + habits with date selection\n"
        "• /dream — log a dream\n"
        "• /thought — quick note\n"
        "• /reflect — answer custom questions\n"
        "• /config — set Google Sheet\n"
        "• /habits_config — habit fields\n"
        "• /questions — manage reflection questions\n\n"
        "Tap /habits (or the button below), pick a date, describe your day in text/voice. I'll show a draft and ask you to confirm."
    ),
    "sheet_reminder": "Please set your Google Sheet via /config first. Example: https://docs.google.com/spreadsheets/d/1AbCDefGh1234567890",
    "habits_restart": "I lost the selected date. Tap /habits and pick a date again.",
    "dream_restart": "Start over with /dream and describe your dream.",
    "thought_restart": "Start over with /thought and send your note.",
    "reflect_restart": "Start over with /reflect to answer the questions.",
    "select_date": "Which date do you want to record?",
    "describe_day": "Describe your day for {date} using text or voice.",
    "processing": "⏳ Processing...",
    "confirm_entry": "Review the draft:\nDate: {date}\nRaw: {raw}\nSummary: {diary}\n\nConfirm?",
    "saved_success": "✅ Saved!",
    "cancelled": "✖ Cancelled.",
    "confirm_generic": "Review and confirm:\n{preview}",
    "error_occurred": "⚠ An error occurred. Please try again.",
    "sheet_not_configured": "⚠ Please configure Google Sheet first via /config.",
    "ask_sheet": "Send a Google Sheet link or ID to store your data.",
    "sheet_saved": "✅ Google Sheet saved. You can now use /habits, /dream, /thought, /reflect.",
    "config_cancelled": "Setup cancelled.",
    "dream_prompt": "Describe your dream (text or voice).",
    "dream_saved": "✅ Dream saved.",
    "thought_prompt": "Share your thought or note (text/voice).",
    "thought_saved": "✅ Thought saved.",
    "reflect_intro": "Answer the questions one by one. Please send your answer:",
    "reflect_done": "✅ Answers saved.",
    "reflect_seeded": "Added default questions. Call /reflect again.",
    "llm_disabled": "Summary disabled: LLM not configured.",
    "voice_disabled": "Voice not available (no STT key). Please send text.",
    "voice_transcribed": "Voice transcription: {text}",
    "help": (
        "Commands:\n"
        "/start — welcome\n"
        "/habits — habits + diary\n"
        "/dream — log a dream\n"
        "/thought — quick thought\n"
        "/reflect — answer custom questions\n"
        "/config — set Google Sheet\n"
        "/habits_config — habit fields\n"
        "/questions — manage reflection questions"
    ),
    "habit_config_intro": "Current habit fields: {fields}\nWhat would you like to do?",
    "habit_add_prompt": "Send a new field as: name | description | type (string/int/bool, defaults to string).",
    "habit_remove_prompt": "Send the field name to remove.",
    "habit_added": "Field added: {name}",
    "habit_removed": "Field removed: {name}",
    "habit_reset": "Habit schema reset to defaults.",
    "question_intro": "Current questions: {questions}\nWhat would you like to do?",
    "question_add_prompt": "Send a question as: id | text. id in latin letters, no spaces.",
    "question_remove_prompt": "Send the question id to remove.",
    "question_added": "Question added: {id}",
    "question_removed": "Question removed: {id}",
    "question_reset": "Questions reset to defaults.",
    "cancelled_config": "Setup cancelled.",
}
