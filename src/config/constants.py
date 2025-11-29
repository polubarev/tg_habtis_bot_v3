from src.models.habit import HabitFieldConfig, HabitSchema

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
    "mood",
    "is_lucid",
    "tags",
    "summary",
]

THOUGHTS_SHEET_COLUMNS = [
    "timestamp",
    "raw_text",
    "tags",
    "category",
]

# Message templates (Russian)
MESSAGES_RU = {
    "welcome": "Привет! Я помогу вести дневник и отслеживать привычки.",
    "select_date": "За какую дату хочешь сделать запись?",
    "describe_day": "Опиши свой день для {date} текстом или голосом.",
    "processing": "⏳ Обрабатываю...",
    "confirm_entry": "Проверь и подтверди:\n\n```json\n{json_data}\n```",
    "saved_success": "✅ Сохранено!",
    "cancelled": "✖ Отменено.",
    "error_occurred": "⚠ Произошла ошибка. Попробуй ещё раз.",
    "sheet_not_configured": "⚠ Сначала подключи Google Sheet через /config.",
}

# Message templates (English)
MESSAGES_EN = {
    "welcome": "Hello! I'll help you keep a diary and track habits.",
    "select_date": "Which date do you want to record?",
    "describe_day": "Describe your day for {date} using text or voice.",
    "processing": "⏳ Processing...",
    "confirm_entry": "Review and confirm:\n\n```json\n{json_data}\n```",
    "saved_success": "✅ Saved!",
    "cancelled": "✖ Cancelled.",
    "error_occurred": "⚠ An error occurred. Please try again.",
    "sheet_not_configured": "⚠ Please configure Google Sheet first via /config.",
}
