def format_confirmation_text(json_preview: str) -> str:
    """Format text shown to the user before saving to Sheets."""

    return f"Please confirm:\n```json\n{json_preview}\n```"

