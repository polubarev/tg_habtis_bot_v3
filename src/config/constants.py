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
    "welcome": "\\u041f\\u0440\\u0438\\u0432\\u0435\\u0442! \\u042f \\u043f\\u043e\\u043c\\u043e\\u0433\\u0443 \\u0432\\u0435\\u0441\\u0442\\u0438 \\u0434\\u043d\\u0435\\u0432\\u043d\\u0438\\u043a \\u0438 \\u043e\\u0442\\u0441\\u043b\\u0435\\u0436\\u0438\\u0432\\u0430\\u0442\\u044c \\u043f\\u0440\\u0438\\u0432\\u044b\\u0447\\u043a\\u0438.",
    "select_date": "\\u0417\\u0430 \\u043a\\u0430\\u043a\\u0443\\u044e \\u0434\\u0430\\u0442\\u0443 \\u0445\\u043e\\u0447\\u0435\\u0448\\u044c \\u0441\\u0434\\u0435\\u043b\\u0430\\u0442\\u044c \\u0437\\u0430\\u043f\\u0438\\u0441\\u044c?",
    "describe_day": "\\u041e\\u043f\\u0438\\u0448\\u0438 \\u0441\\u0432\\u043e\\u0439 \\u0434\\u0435\\u043d\\u044c \\u0434\\u043b\\u044f {date} \\u0442\\u0435\\u043a\\u0441\\u0442\\u043e\\u043c \\u0438\\u043b\\u0438 \\u0433\\u043e\\u043b\\u043e\\u0441\\u043e\\u043c.",
    "processing": "\\u23f3 \\u041e\\u0431\\u0440\\u0430\\u0431\\u0430\\u0442\\u044b\\u0432\\u0430\\u044e...",
    "confirm_entry": "\\u041f\\u0440\\u043e\\u0432\\u0435\\u0440\\u044c \\u0438 \\u043f\\u043e\\u0434\\u0442\\u0432\\u0435\\u0440\\u0434\\u0438:\\n\\n```json\\n{json_data}\\n```",
    "saved_success": "\\u2705 \\u0421\\u043e\\u0445\\u0440\\u0430\\u043d\\u0435\\u043d\\u043e!",
    "cancelled": "\\u2716 \\u041e\\u0442\\u043c\\u0435\\u043d\\u0435\\u043d\\u043e.",
    "error_occurred": "\\u26a0 \\u041f\\u0440\\u043e\\u0438\\u0437\\u043e\\u0448\\u043b\\u0430 \\u043e\\u0448\\u0438\\u0431\\u043a\\u0430. \\u041f\\u043e\\u043f\\u0440\\u043e\\u0431\\u0443\\u0439 \\u0435\\u0449\\u0451 \\u0440\\u0430\\u0437.",
    "sheet_not_configured": "\\u26a0 \\u0421\\u043d\\u0430\\u0447\\u0430\\u043b\\u0430 \\u043f\\u043e\\u0434\\u043a\\u043b\\u044e\\u0447\\u0438 Google Sheet \\u0447\\u0435\\u0440\\u0435\\u0437 /config.",
}

# Message templates (English)
MESSAGES_EN = {
    "welcome": "Hello! I'll help you keep a diary and track habits.",
    "select_date": "Which date do you want to record?",
    "describe_day": "Describe your day for {date} using text or voice.",
    "processing": "\\u23f3 Processing...",
    "confirm_entry": "Review and confirm:\\n\\n```json\\n{json_data}\\n```",
    "saved_success": "\\u2705 Saved!",
    "cancelled": "\\u2716 Cancelled.",
    "error_occurred": "\\u26a0 An error occurred. Please try again.",
    "sheet_not_configured": "\\u26a0 Please configure Google Sheet first via /config.",
}
