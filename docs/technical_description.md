# Habits & Diary Telegram Bot 2.0 – Technical Documentation

> MVP status (this codebase): implemented FastAPI webhook + python-telegram-bot with commands `/start`, `/help`, `/config`, `/habits`, `/dream`, `/thought`, `/reflect`; in-memory session/user store; optional Whisper transcription; optional LLM summary for habits; in-memory Sheets client emulating writes. Real Firestore/Sheets/LLM wiring and full validators are still placeholders.

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Data Models & Schemas](#3-data-models--schemas)
4. [Configuration Management](#4-configuration-management)
5. [Module Specifications](#5-module-specifications)
6. [API Contracts & Interfaces](#6-api-contracts--interfaces)
7. [Database & Storage Layer](#7-database--storage-layer)
8. [LLM Integration Layer](#8-llm-integration-layer)
9. [Telegram Bot Implementation](#9-telegram-bot-implementation)
10. [Speech-to-Text Integration](#10-speech-to-text-integration)
11. [Error Handling & Resilience](#11-error-handling--resilience)
12. [Deployment Guide](#12-deployment-guide)
13. [Testing Strategy](#13-testing-strategy)
14. [Security Considerations](#14-security-considerations)

---

## 1. Architecture Overview

### 1.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TELEGRAM USERS                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GOOGLE CLOUD RUN                                     │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    TELEGRAM WEBHOOK HANDLER                            │  │
│  │  • Request validation                                                  │  │
│  │  • Message routing                                                     │  │
│  │  • Rate limiting                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                                      ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    COMMAND & DIALOG LAYER                              │  │
│  │  • /start, /habits, /dream, /thought, /reflect, /config               │  │
│  │  • Multi-step conversation state machine                               │  │
│  │  • Inline keyboard handlers                                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                    │                 │                    │                  │
│                    ▼                 ▼                    ▼                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  TRANSCRIPTION   │  │   LLM LAYER      │  │  GOOGLE SHEETS LAYER     │   │
│  │  LAYER           │  │  (OpenRouter +   │  │  • Habits tab            │   │
│  │  • Whisper API   │  │   LangChain)     │  │  • Dreams tab            │   │
│  │  • Voice → Text  │  │  • Structured    │  │  • Thoughts tab          │   │
│  └──────────────────┘  │    output        │  │  • Reflections tab       │   │
│                        └──────────────────┘  └──────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    CONFIG & STATE LAYER                                │  │
│  │  • Firestore: user profiles, habit schemas, session state              │  │
│  │  • Secret Manager: API keys, tokens                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
           │  OPENROUTER  │  │   WHISPER    │  │   GOOGLE     │
           │  API         │  │   API        │  │   SHEETS API │
           └──────────────┘  └──────────────┘  └──────────────┘
```

### 1.2 Request Flow Sequence

```
User                    Bot                   Firestore           LLM              Sheets
  │                      │                       │                 │                  │
  │──── /habits ────────▶│                       │                 │                  │
  │                      │──── get_session() ───▶│                 │                  │
  │                      │◀──── session ─────────│                 │                  │
  │◀── "Select date" ────│                       │                 │                  │
  │                      │                       │                 │                  │
  │──── "yesterday" ────▶│                       │                 │                  │
  │                      │──── update_session()─▶│                 │                  │
  │◀── "Describe day" ───│                       │                 │                  │
  │                      │                       │                 │                  │
  │──── [voice msg] ────▶│                       │                 │                  │
  │                      │════ transcribe() ════▶│                 │                  │
  │                      │◀═══ record ════════│                 │                  │
  │                      │──── get_config() ────▶│                 │                  │
  │                      │◀──── habit_schema ────│                 │                  │
  │                      │                       │──── extract()──▶│                  │
  │                      │                       │◀── structured ──│                  │
  │◀── "Confirm JSON" ───│                       │                 │                  │
  │                      │                       │                 │                  │
  │──── "Yes" ──────────▶│                       │                 │                  │
  │                      │                       │                 │──── append() ───▶│
  │                      │                       │                 │◀──── OK ─────────│
  │◀── "Saved!" ─────────│                       │                 │                  │
```

### 1.3 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Runtime | Python | 3.11+ | Main application language |
| Web Framework | FastAPI | 0.104+ | Webhook handling, async support |
| Telegram | python-telegram-bot | 20.x | Telegram Bot API wrapper |
| LLM Framework | LangChain | 0.1+ | Prompt management, structured output |
| LLM Provider | OpenRouter | latest | Multi-model LLM access |
| STT | OpenAI Whisper API | v1 | Speech-to-text |
| Database | Google Firestore | native | User config, session state |
| Storage | Google Sheets API | v4 | User data persistence |
| Secrets | Google Secret Manager | latest | Credential management |
| Container | Docker | latest | Application containerization |
| Hosting | Google Cloud Run | gen2 | Serverless deployment |

---

## 2. Project Structure

### 2.1 Directory Layout

```
habits-diary-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py             # Application settings (Pydantic)
│   │   └── constants.py            # Static constants
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                 # User profile models
│   │   ├── habit.py                # Habit schema models
│   │   ├── entry.py                # Entry models (habit, dream, thought)
│   │   ├── session.py              # Conversation session models
│   │   └── enums.py                # Enumerations
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── telegram/
│   │   │   ├── __init__.py
│   │   │   ├── bot.py              # Bot initialization
│   │   │   ├── handlers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── start.py        # /start command
│   │   │   │   ├── habits.py       # /habits command
│   │   │   │   ├── dream.py        # /dream command
│   │   │   │   ├── thought.py      # /thought command
│   │   │   │   ├── reflect.py      # /reflect command
│   │   │   │   ├── config.py       # /config command
│   │   │   │   ├── help.py         # /help command
│   │   │   │   └── callbacks.py    # Inline button callbacks
│   │   │   ├── keyboards.py        # Keyboard builders
│   │   │   └── utils.py            # Telegram utilities
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # OpenRouter client setup
│   │   │   ├── prompts/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── habits.py       # Habit extraction prompts
│   │   │   │   ├── dreams.py       # Dream metadata prompts
│   │   │   │   ├── thoughts.py     # Thought tagging prompts
│   │   │   │   └── templates.py    # Shared prompt templates
│   │   │   ├── extractors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── habit_extractor.py
│   │   │   │   ├── dream_extractor.py
│   │   │   │   └── thought_extractor.py
│   │   │   └── schemas.py          # Dynamic Pydantic schema builder
│   │   │
│   │   ├── transcription/
│   │   │   ├── __init__.py
│   │   │   ├── whisper.py          # Whisper API client
│   │   │   └── audio_utils.py      # Audio processing utilities
│   │   │
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── firestore/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── client.py       # Firestore client
│   │   │   │   ├── user_repo.py    # User repository
│   │   │   │   └── session_repo.py # Session repository
│   │   │   └── sheets/
│   │   │       ├── __init__.py
│   │   │       ├── client.py       # Google Sheets client
│   │   │       ├── habits_sheet.py # Habits sheet operations
│   │   │       ├── dreams_sheet.py # Dreams sheet operations
│   │   │       ├── thoughts_sheet.py
│   │   │       ├── reflections_sheet.py
│   │   │       └── validators.py   # Sheet structure validators
│   │   │
│   │   └── secrets/
│   │       ├── __init__.py
│   │       └── manager.py          # Secret Manager integration
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py           # Custom exceptions
│   │   ├── logging.py              # Logging configuration
│   │   └── dependencies.py         # FastAPI dependencies
│   │
│   └── utils/
│       ├── __init__.py
│       ├── date_parser.py          # Natural language date parsing
│       ├── validators.py           # Input validators
│       └── formatters.py           # Output formatters
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_extractors.py
│   │   ├── test_date_parser.py
│   │   └── test_validators.py
│   ├── integration/
│   │   ├── test_llm_integration.py
│   │   ├── test_sheets_integration.py
│   │   └── test_firestore_integration.py
│   └── e2e/
│       └── test_conversation_flows.py
│
├── scripts/
│   ├── setup_webhook.py            # Webhook registration script
│   ├── migrate_data.py             # Data migration utilities
│   └── seed_test_data.py           # Test data seeding
│
├── Dockerfile
├── docker-compose.yml              # Local development
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .gitignore
├── cloudbuild.yaml                 # Cloud Build config
└── README.md
```

### 2.2 Module Dependency Graph

```
                    ┌─────────────┐
                    │   main.py   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  config/   │  │   core/    │  │ services/  │
    │  settings  │  │ exceptions │  │  telegram  │
    └────────────┘  │  logging   │  └─────┬──────┘
                    └────────────┘        │
                           ▲              │
                           │    ┌─────────┴─────────┐
                           │    ▼                   ▼
                    ┌────────────┐           ┌────────────┐
                    │  models/   │◀──────────│ handlers/  │
                    └────────────┘           └─────┬──────┘
                           ▲                       │
           ┌───────────────┼───────────────┬───────┘
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │   llm/     │  │ storage/   │  │transcription│
    │ extractors │  │  sheets    │  │  whisper   │
    └────────────┘  │  firestore │  └────────────┘
                    └────────────┘
```

---

## 3. Data Models & Schemas

### 3.1 User Profile Model

```python
# src/models/user.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HabitFieldConfig(BaseModel):
    """Configuration for a single habit field."""
    type: str | list[str]  # "integer", "string", ["integer", "null"]
    description: str
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    default: Optional[any] = None
    required: bool = True


class HabitSchema(BaseModel):
    """Complete habit schema for a user."""
    fields: dict[str, HabitFieldConfig]
    version: int = 1
    
    class Config:
        extra = "forbid"


class CustomQuestion(BaseModel):
    """User-defined reflection question."""
    id: str  # Stable identifier (e.g., "gratitude", "goal_progress")
    text: str  # Question text
    language: str = "ru"
    active: bool = True


class UserProfile(BaseModel):
    """Complete user profile stored in Firestore."""
    telegram_user_id: int
    telegram_username: Optional[str] = None
    
    # Google Sheets configuration
    sheet_id: Optional[str] = None
    sheet_url: Optional[str] = None
    sheets_validated: bool = False
    
    # Habit configuration
    habit_schema: HabitSchema
    
    # Reflection questions
    custom_questions: list[CustomQuestion] = Field(default_factory=list)
    
    # User preferences
    language: str = "ru"
    timezone: str = "Europe/Moscow"
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    onboarding_completed: bool = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### 3.2 Entry Models

```python
# src/models/entry.py

from datetime import datetime, date
from typing import Optional, Any
from pydantic import BaseModel, Field


class HabitEntry(BaseModel):
    """A single habit entry to be written to Google Sheets."""
    date: date
    raw_record: str  # Original user input (text or transcription)
    diary: Optional[str] = None  # LLM-generated summary
    
    # Dynamic fields based on user's habit schema
    # These will be added dynamically
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "telegram"  # "telegram", "api", "import"
    input_type: str = "text"  # "text", "voice"
    
    def to_sheet_row(self, field_order: list[str]) -> list[Any]:
        """Convert entry to a row for Google Sheets."""
        row = [self.date.isoformat()]
        for field in field_order:
            if field == "raw_record":
                row.append(self.raw_record)
            elif field == "diary":
                row.append(self.diary or "")
            else:
                row.append(self.extra_fields.get(field, ""))
        return row


class DreamEntry(BaseModel):
    """A dream log entry."""
    timestamp: datetime
    date: date
    record: str
    
    # LLM-extracted metadata (optional)
    mood: Optional[str] = None
    is_lucid: Optional[bool] = None
    tags: list[str] = Field(default_factory=list)
    
    # Optional summary
    summary: Optional[str] = None


class ThoughtEntry(BaseModel):
    """A quick thought or note."""
    timestamp: datetime
    record: str
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None  # "idea", "reminder", "observation"


class ReflectionEntry(BaseModel):
    """Answers to reflection questions."""
    date: date
    answers: dict[str, str]  # question_id -> answer text
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 3.3 Session State Models

```python
# src/models/session.py

from datetime import datetime, date
from typing import Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """Possible states in a conversation flow."""
    IDLE = "idle"
    
    # Habits flow
    HABITS_AWAITING_DATE = "habits_awaiting_date"
    HABITS_AWAITING_CONTENT = "habits_awaiting_content"
    HABITS_AWAITING_CONFIRMATION = "habits_awaiting_confirmation"
    HABITS_AWAITING_EDIT = "habits_awaiting_edit"
    
    # Dream flow
    DREAM_AWAITING_CONTENT = "dream_awaiting_content"
    DREAM_AWAITING_CONFIRMATION = "dream_awaiting_confirmation"
    
    # Thought flow
    THOUGHT_AWAITING_CONTENT = "thought_awaiting_content"
    
    # Reflect flow
    REFLECT_ANSWERING_QUESTIONS = "reflect_answering_questions"
    REFLECT_AWAITING_CONFIRMATION = "reflect_awaiting_confirmation"
    
    # Config flow
    CONFIG_AWAITING_SHEET_URL = "config_awaiting_sheet_url"
    CONFIG_EDITING_HABITS = "config_editing_habits"
    CONFIG_ADDING_QUESTION = "config_adding_question"
    
    # Onboarding
    ONBOARDING_WELCOME = "onboarding_welcome"
    ONBOARDING_SHEET_SETUP = "onboarding_sheet_setup"
    ONBOARDING_HABIT_REVIEW = "onboarding_habit_review"


class SessionData(BaseModel):
    """Conversation session data stored in Firestore."""
    user_id: int
    state: ConversationState = ConversationState.IDLE
    
    # Context data for current flow
    selected_date: Optional[date] = None
    pending_entry: Optional[dict[str, Any]] = None
    current_question_index: Optional[int] = None
    reflection_answers: dict[str, str] = Field(default_factory=dict)
    
    # Temporary storage
    temp_data: dict[str, Any] = Field(default_factory=dict)
    
    # Session metadata
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def reset(self) -> None:
        """Reset session to idle state."""
        self.state = ConversationState.IDLE
        self.selected_date = None
        self.pending_entry = None
        self.current_question_index = None
        self.reflection_answers = {}
        self.temp_data = {}
```

### 3.4 Enumerations

```python
# src/models/enums.py

from enum import Enum


class InputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class EntryType(str, Enum):
    HABIT = "habit"
    DREAM = "dream"
    THOUGHT = "thought"
    REFLECTION = "reflection"


class SheetTab(str, Enum):
    HABITS = "Habits"
    DREAMS = "Dreams"
    THOUGHTS = "Thoughts"
    REFLECTIONS = "Reflections"


class Language(str, Enum):
    RUSSIAN = "ru"
    ENGLISH = "en"


class CallbackAction(str, Enum):
    """Actions for inline keyboard callbacks."""
    # Date selection
    DATE_TODAY = "date_today"
    DATE_YESTERDAY = "date_yesterday"
    DATE_CUSTOM = "date_custom"
    
    # Confirmation
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    CONFIRM_EDIT = "confirm_edit"
    
    # Entry type selection
    ENTRY_HABITS = "entry_habits"
    ENTRY_DREAM = "entry_dream"
    ENTRY_THOUGHT = "entry_thought"
    ENTRY_REFLECT = "entry_reflect"
    
    # Config actions
    CONFIG_SHEET = "config_sheet"
    CONFIG_HABITS = "config_habits"
    CONFIG_QUESTIONS = "config_questions"
    
    # Navigation
    NAV_BACK = "nav_back"
    NAV_CANCEL = "nav_cancel"
    NAV_SKIP = "nav_skip"
```

---

## 4. Configuration Management

### 4.1 Application Settings

```python
# src/config/settings.py

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # Application
    app_name: str = "Habits Diary Bot"
    app_version: str = "2.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Google Cloud
    gcp_project_id: str
    gcp_region: str = "europe-west1"
    
    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: str = Field(default="")
    
    # OpenRouter / LLM
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-3-5-sonnet"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    
    # Whisper / STT
    openai_api_key: str  # For Whisper API
    whisper_model: str = "whisper-1"
    
    # Firestore
    firestore_collection_users: str = "users"
    firestore_collection_sessions: str = "sessions"
    
    # Session
    session_ttl_minutes: int = 60
    
    # Rate limiting
    rate_limit_requests_per_minute: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### 4.2 Constants

```python
# src/config/constants.py

from src.models.user import HabitFieldConfig, HabitSchema

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
        "raw_record": HabitFieldConfig(
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
    "raw_record",
    "diary",
]

DREAMS_SHEET_COLUMNS = [
    "timestamp",
    "date",
    "record",
    "mood",
    "is_lucid",
    "tags",
    "summary",
]

THOUGHTS_SHEET_COLUMNS = [
    "timestamp",
    "record",
    "tags",
    "category",
]

# Message templates (Russian)
MESSAGES_RU = {
    "welcome": "👋 Привет! Я помогу тебе вести дневник и отслеживать привычки.",
    "select_date": "📅 За какую дату ты хочешь записать?",
    "describe_day": "Опиши свой день за {date} текстом или голосовым сообщением.",
    "processing": "⏳ Обрабатываю...",
    "confirm_entry": "Проверь данные и подтверди:\n\n```json\n{json_data}\n```",
    "saved_success": "✅ Сохранено!",
    "cancelled": "❌ Отменено.",
    "error_occurred": "⚠️ Произошла ошибка. Попробуй ещё раз.",
    "sheet_not_configured": "⚠️ Сначала настрой Google Sheet через /config.",
}

MESSAGES_EN = {
    "welcome": "👋 Hello! I'll help you keep a diary and track habits.",
    "select_date": "📅 For which date do you want to record?",
    "describe_day": "Describe your day for {date} using text or voice message.",
    "processing": "⏳ Processing...",
    "confirm_entry": "Review and confirm:\n\n```json\n{json_data}\n```",
    "saved_success": "✅ Saved!",
    "cancelled": "❌ Cancelled.",
    "error_occurred": "⚠️ An error occurred. Please try again.",
    "sheet_not_configured": "⚠️ Please configure Google Sheet first via /config.",
}
```

---

## 5. Module Specifications

### 5.1 Core Exceptions

```python
# src/core/exceptions.py

from typing import Optional


class BotException(Exception):
    """Base exception for all bot errors."""
    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(message)
        self.user_message = user_message or "An error occurred. Please try again."


class ConfigurationError(BotException):
    """Raised when user configuration is invalid or missing."""
    pass


class SheetNotConfiguredError(ConfigurationError):
    """Raised when Google Sheet is not configured."""
    def __init__(self):
        super().__init__(
            "Google Sheet not configured",
            user_message="Please configure your Google Sheet first using /config."
        )


class SheetValidationError(BotException):
    """Raised when sheet structure is invalid."""
    pass


class TranscriptionError(BotException):
    """Raised when audio transcription fails."""
    pass


class LLMError(BotException):
    """Raised when LLM request fails."""
    pass


class ExtractionError(LLMError):
    """Raised when structured extraction fails."""
    pass


class SessionExpiredError(BotException):
    """Raised when conversation session has expired."""
    def __init__(self):
        super().__init__(
            "Session expired",
            user_message="Session expired. Please start again."
        )


class RateLimitError(BotException):
    """Raised when rate limit is exceeded."""
    def __init__(self):
        super().__init__(
            "Rate limit exceeded",
            user_message="Too many requests. Please wait a moment."
        )


class ValidationError(BotException):
    """Raised when input validation fails."""
    pass
```

### 5.2 Logging Configuration

```python
# src/core/logging.py

import logging
import sys
from typing import Optional
import structlog
from src.config.settings import get_settings


def setup_logging(log_level: Optional[str] = None) -> None:
    """Configure structured logging for the application."""
    settings = get_settings()
    level = log_level or settings.log_level
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if not settings.debug
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Also configure standard logging for third-party libraries
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )
    
    # Reduce noise from third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)
```

### 5.3 FastAPI Dependencies

```python
# src/core/dependencies.py

from typing import Annotated
from fastapi import Depends, Header, HTTPException, Request
from src.config.settings import get_settings, Settings
from src.services.storage.firestore.user_repo import UserRepository
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.llm.client import LLMClient
from src.services.transcription.whisper import WhisperClient
from src.services.storage.sheets.client import SheetsClient


async def get_user_repo() -> UserRepository:
    """Dependency for user repository."""
    return UserRepository()


async def get_session_repo() -> SessionRepository:
    """Dependency for session repository."""
    return SessionRepository()


async def get_llm_client() -> LLMClient:
    """Dependency for LLM client."""
    return LLMClient()


async def get_whisper_client() -> WhisperClient:
    """Dependency for Whisper client."""
    return WhisperClient()


async def get_sheets_client() -> SheetsClient:
    """Dependency for Google Sheets client."""
    return SheetsClient()


async def verify_telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> bool:
    """Verify the webhook request is from Telegram."""
    settings = get_settings()
    
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid secret token")
    
    return True


# Type aliases for dependency injection
UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
SessionRepoDep = Annotated[SessionRepository, Depends(get_session_repo)]
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
WhisperClientDep = Annotated[WhisperClient, Depends(get_whisper_client)]
SheetsClientDep = Annotated[SheetsClient, Depends(get_sheets_client)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
```

---

## 6. API Contracts & Interfaces

### 6.1 Repository Interfaces

```python
# src/services/storage/interfaces.py

from abc import ABC, abstractmethod
from typing import Optional
from datetime import date
from src.models.user import UserProfile
from src.models.session import SessionData
from src.models.entry import HabitEntry, DreamEntry, ThoughtEntry, ReflectionEntry


class IUserRepository(ABC):
    """Interface for user data persistence."""
    
    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        """Get user profile by Telegram ID."""
        pass
    
    @abstractmethod
    async def create(self, user: UserProfile) -> UserProfile:
        """Create a new user profile."""
        pass
    
    @abstractmethod
    async def update(self, user: UserProfile) -> UserProfile:
        """Update an existing user profile."""
        pass
    
    @abstractmethod
    async def delete(self, telegram_id: int) -> bool:
        """Delete a user profile."""
        pass


class ISessionRepository(ABC):
    """Interface for session state persistence."""
    
    @abstractmethod
    async def get(self, user_id: int) -> Optional[SessionData]:
        """Get session for user."""
        pass
    
    @abstractmethod
    async def save(self, session: SessionData) -> SessionData:
        """Save or update session."""
        pass
    
    @abstractmethod
    async def delete(self, user_id: int) -> bool:
        """Delete session."""
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of deleted sessions."""
        pass


class ISheetWriter(ABC):
    """Interface for writing entries to Google Sheets."""
    
    @abstractmethod
    async def append_habit(
        self,
        sheet_id: str,
        entry: HabitEntry,
        field_order: list[str],
    ) -> bool:
        """Append a habit entry to the Habits sheet."""
        pass
    
    @abstractmethod
    async def append_dream(self, sheet_id: str, entry: DreamEntry) -> bool:
        """Append a dream entry to the Dreams sheet."""
        pass
    
    @abstractmethod
    async def append_thought(self, sheet_id: str, entry: ThoughtEntry) -> bool:
        """Append a thought entry to the Thoughts sheet."""
        pass
    
    @abstractmethod
    async def append_reflection(
        self,
        sheet_id: str,
        entry: ReflectionEntry,
        question_ids: list[str],
    ) -> bool:
        """Append reflection answers."""
        pass
    
    @abstractmethod
    async def validate_structure(
        self,
        sheet_id: str,
        required_tabs: list[str],
    ) -> dict[str, bool]:
        """Validate sheet structure. Returns dict of tab -> exists."""
        pass
    
    @abstractmethod
    async def create_missing_tabs(
        self,
        sheet_id: str,
        tabs: list[str],
    ) -> list[str]:
        """Create missing tabs. Returns list of created tab names."""
        pass
```

### 6.2 Extractor Interfaces

```python
# src/services/llm/interfaces.py

from abc import ABC, abstractmethod
from typing import Any
from src.models.user import HabitSchema
from src.models.entry import HabitEntry, DreamEntry, ThoughtEntry


class IHabitExtractor(ABC):
    """Interface for extracting structured habit data from text."""
    
    @abstractmethod
    async def extract(
        self,
        text: str,
        schema: HabitSchema,
        language: str = "ru",
    ) -> dict[str, Any]:
        """
        Extract habit data from free-form text.
        
        Args:
            text: The raw user input (text or transcription).
            schema: The user's habit schema configuration.
            language: Expected language of the input.
            
        Returns:
            Dictionary with extracted field values.
            
        Raises:
            ExtractionError: If extraction fails.
        """
        pass


class IDreamExtractor(ABC):
    """Interface for extracting dream metadata."""
    
    @abstractmethod
    async def extract(
        self,
        text: str,
        language: str = "ru",
    ) -> dict[str, Any]:
        """
        Extract dream metadata from text.
        
        Returns dict with: mood, is_lucid, tags, summary
        """
        pass


class IThoughtTagger(ABC):
    """Interface for tagging thoughts."""
    
    @abstractmethod
    async def tag(
        self,
        text: str,
        language: str = "ru",
    ) -> dict[str, Any]:
        """
        Tag a thought with categories and keywords.
        
        Returns dict with: tags, category
        """
        pass
```

### 6.3 Transcription Interface

```python
# src/services/transcription/interfaces.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration_seconds: Optional[float] = None


class ITranscriber(ABC):
    """Interface for speech-to-text services."""
    
    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        format: str = "ogg",
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Raw audio bytes.
            format: Audio format (ogg, mp3, wav, etc.).
            language_hint: Expected language (ISO code, e.g., "ru").
            
        Returns:
            TranscriptionResult with text and metadata.
            
        Raises:
            TranscriptionError: If transcription fails.
        """
        pass
    
    @abstractmethod
    async def transcribe_file(
        self,
        file_path: str,
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio from file path."""
        pass
```

---

## 7. Database & Storage Layer

### 7.1 Firestore Client

```python
# src/services/storage/firestore/client.py

from typing import Optional
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient
from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncClient] = None


async def get_firestore_client() -> AsyncClient:
    """Get or create Firestore async client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncClient(project=settings.gcp_project_id)
        logger.info("Firestore client initialized", project=settings.gcp_project_id)
    return _client


async def close_firestore_client() -> None:
    """Close Firestore client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("Firestore client closed")
```

### 7.2 User Repository Implementation

```python
# src/services/storage/firestore/user_repo.py

from typing import Optional
from datetime import datetime
from google.cloud.firestore_v1 import AsyncDocumentReference
from src.services.storage.firestore.client import get_firestore_client
from src.services.storage.interfaces import IUserRepository
from src.models.user import UserProfile
from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class UserRepository(IUserRepository):
    """Firestore implementation of user repository."""
    
    def __init__(self):
        self._collection_name = get_settings().firestore_collection_users
    
    async def _get_collection(self):
        client = await get_firestore_client()
        return client.collection(self._collection_name)
    
    def _user_doc_id(self, telegram_id: int) -> str:
        return f"tg_{telegram_id}"
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        """Get user profile by Telegram ID."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._user_doc_id(telegram_id))
        doc = await doc_ref.get()
        
        if not doc.exists:
            logger.debug("User not found", telegram_id=telegram_id)
            return None
        
        data = doc.to_dict()
        logger.debug("User loaded", telegram_id=telegram_id)
        return UserProfile(**data)
    
    async def create(self, user: UserProfile) -> UserProfile:
        """Create a new user profile."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._user_doc_id(user.telegram_user_id))
        
        user.created_at = datetime.utcnow()
        user.updated_at = user.created_at
        
        await doc_ref.set(user.model_dump(mode="json"))
        logger.info("User created", telegram_id=user.telegram_user_id)
        return user
    
    async def update(self, user: UserProfile) -> UserProfile:
        """Update an existing user profile."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._user_doc_id(user.telegram_user_id))
        
        user.updated_at = datetime.utcnow()
        
        await doc_ref.update(user.model_dump(mode="json"))
        logger.info("User updated", telegram_id=user.telegram_user_id)
        return user
    
    async def delete(self, telegram_id: int) -> bool:
        """Delete a user profile."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._user_doc_id(telegram_id))
        
        await doc_ref.delete()
        logger.info("User deleted", telegram_id=telegram_id)
        return True
    
    async def exists(self, telegram_id: int) -> bool:
        """Check if user exists."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._user_doc_id(telegram_id))
        doc = await doc_ref.get()
        return doc.exists
```

### 7.3 Session Repository Implementation

```python
# src/services/storage/firestore/session_repo.py

from typing import Optional
from datetime import datetime, timedelta
from src.services.storage.firestore.client import get_firestore_client
from src.services.storage.interfaces import ISessionRepository
from src.models.session import SessionData, ConversationState
from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class SessionRepository(ISessionRepository):
    """Firestore implementation of session repository."""
    
    def __init__(self):
        settings = get_settings()
        self._collection_name = settings.firestore_collection_sessions
        self._ttl_minutes = settings.session_ttl_minutes
    
    async def _get_collection(self):
        client = await get_firestore_client()
        return client.collection(self._collection_name)
    
    def _session_doc_id(self, user_id: int) -> str:
        return f"session_{user_id}"
    
    async def get(self, user_id: int) -> Optional[SessionData]:
        """Get session for user."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._session_doc_id(user_id))
        doc = await doc_ref.get()
        
        if not doc.exists:
            return None
        
        session = SessionData(**doc.to_dict())
        
        # Check expiration
        if session.is_expired():
            await self.delete(user_id)
            return None
        
        return session
    
    async def save(self, session: SessionData) -> SessionData:
        """Save or update session."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._session_doc_id(session.user_id))
        
        session.last_activity = datetime.utcnow()
        session.expires_at = session.last_activity + timedelta(minutes=self._ttl_minutes)
        
        await doc_ref.set(session.model_dump(mode="json"))
        logger.debug("Session saved", user_id=session.user_id, state=session.state)
        return session
    
    async def delete(self, user_id: int) -> bool:
        """Delete session."""
        collection = await self._get_collection()
        doc_ref = collection.document(self._session_doc_id(user_id))
        await doc_ref.delete()
        logger.debug("Session deleted", user_id=user_id)
        return True
    
    async def get_or_create(self, user_id: int) -> SessionData:
        """Get existing session or create new one."""
        session = await self.get(user_id)
        if session is None:
            session = SessionData(user_id=user_id)
            await self.save(session)
        return session
    
    async def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        collection = await self._get_collection()
        now = datetime.utcnow()
        
        # Query expired sessions
        query = collection.where("expires_at", "<", now)
        docs = await query.get()
        
        count = 0
        for doc in docs:
            await doc.reference.delete()
            count += 1
        
        if count > 0:
            logger.info("Cleaned up expired sessions", count=count)
        
        return count
```

### 7.4 Google Sheets Client

```python
# src/services/storage/sheets/client.py

from typing import Optional, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import asyncio
from functools import partial

from src.config.settings import get_settings
from src.core.logging import get_logger
from src.core.exceptions import SheetValidationError

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    """Google Sheets API client."""
    
    def __init__(self, credentials_path: Optional[str] = None):
        self._credentials_path = credentials_path
        self._service = None
    
    def _get_service(self):
        """Get or create Sheets API service."""
        if self._service is None:
            if self._credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self._credentials_path,
                    scopes=SCOPES,
                )
            else:
                # Use default credentials (Cloud Run)
                from google.auth import default
                credentials, _ = default(scopes=SCOPES)
            
            self._service = build("sheets", "v4", credentials=credentials)
            logger.info("Sheets service initialized")
        return self._service
    
    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous API call in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))
    
    async def get_sheet_metadata(self, sheet_id: str) -> dict:
        """Get spreadsheet metadata including sheet/tab names."""
        service = self._get_service()
        
        def _get():
            return service.spreadsheets().get(
                spreadsheetId=sheet_id,
                fields="sheets.properties.title,sheets.properties.sheetId"
            ).execute()
        
        result = await self._run_sync(_get)
        return result
    
    async def get_existing_tabs(self, sheet_id: str) -> list[str]:
        """Get list of existing tab names in spreadsheet."""
        metadata = await self.get_sheet_metadata(sheet_id)
        return [
            sheet["properties"]["title"]
            for sheet in metadata.get("sheets", [])
        ]
    
    async def create_tab(self, sheet_id: str, tab_name: str) -> bool:
        """Create a new tab/sheet."""
        service = self._get_service()
        
        def _create():
            body = {
                "requests": [{
                    "addSheet": {
                        "properties": {"title": tab_name}
                    }
                }]
            }
            return service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body=body
            ).execute()
        
        try:
            await self._run_sync(_create)
            logger.info("Tab created", sheet_id=sheet_id, tab_name=tab_name)
            return True
        except HttpError as e:
            logger.error("Failed to create tab", error=str(e))
            raise SheetValidationError(f"Failed to create tab: {e}")
    
    async def append_row(
        self,
        sheet_id: str,
        tab_name: str,
        values: list[Any],
    ) -> bool:
        """Append a single row to a sheet tab."""
        service = self._get_service()
        range_name = f"{tab_name}!A:Z"
        
        def _append():
            body = {"values": [values]}
            return service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()
        
        try:
            result = await self._run_sync(_append)
            logger.debug(
                "Row appended",
                sheet_id=sheet_id,
                tab_name=tab_name,
                updates=result.get("updates", {}),
            )
            return True
        except HttpError as e:
            logger.error("Failed to append row", error=str(e))
            raise SheetValidationError(f"Failed to append row: {e}")
    
    async def get_header_row(
        self,
        sheet_id: str,
        tab_name: str,
    ) -> list[str]:
        """Get the header row (first row) of a tab."""
        service = self._get_service()
        range_name = f"{tab_name}!1:1"
        
        def _get():
            return service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name,
            ).execute()
        
        result = await self._run_sync(_get)
        values = result.get("values", [[]])
        return values[0] if values else []
    
    async def set_header_row(
        self,
        sheet_id: str,
        tab_name: str,
        headers: list[str],
    ) -> bool:
        """Set the header row for a tab."""
        service = self._get_service()
        range_name = f"{tab_name}!1:1"
        
        def _update():
            body = {"values": [headers]}
            return service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body,
            ).execute()
        
        await self._run_sync(_update)
        logger.debug("Header row set", sheet_id=sheet_id, tab_name=tab_name)
        return True
    
    async def validate_and_setup_structure(
        self,
        sheet_id: str,
        required_tabs: dict[str, list[str]],
    ) -> dict[str, bool]:
        """
        Validate and set up sheet structure.
        
        Args:
            sheet_id: Google Sheet ID
            required_tabs: Dict of tab_name -> required_columns
            
        Returns:
            Dict of tab_name -> was_created
        """
        results = {}
        existing_tabs = await self.get_existing_tabs(sheet_id)
        
        for tab_name, columns in required_tabs.items():
            if tab_name not in existing_tabs:
                await self.create_tab(sheet_id, tab_name)
                await self.set_header_row(sheet_id, tab_name, columns)
                results[tab_name] = True
            else:
                # Check if headers exist
                headers = await self.get_header_row(sheet_id, tab_name)
                if not headers:
                    await self.set_header_row(sheet_id, tab_name, columns)
                results[tab_name] = False
        
        return results
```

### 7.5 Habits Sheet Operations

```python
# src/services/storage/sheets/habits_sheet.py

from datetime import date
from typing import Any

from src.services.storage.sheets.client import SheetsClient
from src.models.entry import HabitEntry
from src.models.enums import SheetTab
from src.config.constants import HABITS_SHEET_COLUMNS
from src.core.logging import get_logger

logger = get_logger(__name__)


class HabitsSheetService:
    """Service for habits sheet operations."""
    
    def __init__(self, sheets_client: SheetsClient):
        self._client = sheets_client
        self._tab_name = SheetTab.HABITS.value
    
    async def append_entry(
        self,
        sheet_id: str,
        entry: HabitEntry,
        field_order: list[str] | None = None,
    ) -> bool:
        """
        Append a habit entry to the Habits sheet.
        
        Args:
            sheet_id: Google Sheet ID
            entry: HabitEntry to append
            field_order: Custom field order (uses default if None)
        """
        columns = field_order or HABITS_SHEET_COLUMNS
        row = self._entry_to_row(entry, columns)
        
        success = await self._client.append_row(
            sheet_id=sheet_id,
            tab_name=self._tab_name,
            values=row,
        )
        
        if success:
            logger.info(
                "Habit entry saved",
                sheet_id=sheet_id,
                date=entry.date.isoformat(),
            )
        
        return success
    
    def _entry_to_row(
        self,
        entry: HabitEntry,
        columns: list[str],
    ) -> list[Any]:
        """Convert HabitEntry to row values."""
        row = []
        for col in columns:
            if col == "date":
                row.append(entry.date.isoformat())
            elif col == "raw_record":
                row.append(entry.raw_record)
            elif col == "diary":
                row.append(entry.diary or "")
            elif col in entry.extra_fields:
                value = entry.extra_fields[col]
                # Convert None to empty string for sheets
                row.append("" if value is None else value)
            else:
                row.append("")
        return row
    
    async def check_date_exists(
        self,
        sheet_id: str,
        check_date: date,
    ) -> bool:
        """Check if an entry for the given date already exists."""
        # Note: For full implementation, would need to read date column
        # This is a placeholder for the interface
        return False
    
    async def update_entry(
        self,
        sheet_id: str,
        entry: HabitEntry,
        field_order: list[str] | None = None,
    ) -> bool:
        """Update an existing entry (find by date and overwrite)."""
        # Placeholder for update functionality
        # Would need to find row by date and update
        raise NotImplementedError("Update not yet implemented")
```

---

## 8. LLM Integration Layer

### 8.1 LLM Client Setup

```python
# src/services/llm/client.py

from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """OpenRouter LLM client wrapper."""
    
    def __init__(self):
        settings = get_settings()
        self._model = ChatOpenAI(
            model=settings.llm_model,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            default_headers={
                "HTTP-Referer": "https://habits-diary-bot.app",
                "X-Title": "Habits Diary Bot",
            },
        )
        logger.info(
            "LLM client initialized",
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )
    
    @property
    def model(self) -> BaseChatModel:
        """Get the underlying LangChain model."""
        return self._model
    
    def with_structured_output(self, schema: type) -> BaseChatModel:
        """
        Return model configured for structured output.
        
        Args:
            schema: Pydantic model class for output structure.
        """
        return self._model.with_structured_output(schema)
```

### 8.2 Dynamic Schema Builder

```python
# src/services/llm/schemas.py

from typing import Any, Optional, Type
from pydantic import BaseModel, Field, create_model
from src.models.user import HabitSchema, HabitFieldConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


def build_habit_extraction_schema(
    habit_schema: HabitSchema,
    include_diary: bool = True,
) -> Type[BaseModel]:
    """
    Dynamically build a Pydantic model from user's habit schema.
    
    Args:
        habit_schema: User's habit configuration
        include_diary: Whether to include diary summary field
        
    Returns:
        Dynamically created Pydantic model class
    """
    field_definitions = {}
    
    for field_name, field_config in habit_schema.fields.items():
        # Skip raw_record - it's always the original input, not extracted
        if field_name == "raw_record":
            continue
        
        # Skip diary if not requested
        if field_name == "diary" and not include_diary:
            continue
        
        python_type = _config_to_python_type(field_config)
        default = ... if field_config.required else None
        
        field_definitions[field_name] = (
            python_type,
            Field(
                default=default,
                description=field_config.description,
                ge=field_config.minimum,
                le=field_config.maximum,
            ),
        )
    
    # Create the dynamic model
    model = create_model(
        "HabitExtraction",
        **field_definitions,
    )
    
    logger.debug(
        "Built extraction schema",
        fields=list(field_definitions.keys()),
    )
    
    return model


def _config_to_python_type(config: HabitFieldConfig) -> type:
    """Convert HabitFieldConfig type to Python type annotation."""
    type_spec = config.type
    
    if isinstance(type_spec, list):
        # Handle nullable types like ["integer", "null"]
        if "null" in type_spec:
            non_null = [t for t in type_spec if t != "null"][0]
            base_type = _type_string_to_python(non_null)
            return Optional[base_type]
        else:
            return _type_string_to_python(type_spec[0])
    else:
        return _type_string_to_python(type_spec)


def _type_string_to_python(type_str: str) -> type:
    """Convert JSON schema type string to Python type."""
    type_map = {
        "integer": int,
        "number": float,
        "string": str,
        "boolean": bool,
    }
    return type_map.get(type_str, str)


# Pre-defined schemas for dreams and thoughts

class DreamExtraction(BaseModel):
    """Schema for dream metadata extraction."""
    mood: Optional[str] = Field(
        default=None,
        description="Overall mood of the dream (e.g., 'happy', 'scary', 'confused', 'neutral')",
    )
    is_lucid: Optional[bool] = Field(
        default=None,
        description="Whether the dream was lucid (person was aware they were dreaming)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Key themes or elements in the dream (e.g., 'flying', 'water', 'family')",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Brief summary of the dream in 1-2 sentences, same language as input",
    )


class ThoughtExtraction(BaseModel):
    """Schema for thought tagging."""
    tags: list[str] = Field(
        default_factory=list,
        description="Relevant tags for the thought (max 5)",
    )
    category: Optional[str] = Field(
        default=None,
        description="Category: 'idea', 'reminder', 'observation', 'question', or 'other'",
    )
```

### 8.3 Habit Extractor Implementation

```python
# src/services/llm/extractors/habit_extractor.py

from typing import Any, Type
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from src.services.llm.client import LLMClient
from src.services.llm.schemas import build_habit_extraction_schema
from src.services.llm.interfaces import IHabitExtractor
from src.models.user import HabitSchema
from src.core.exceptions import ExtractionError
from src.core.logging import get_logger

logger = get_logger(__name__)

HABIT_EXTRACTION_PROMPT = """You are a helpful assistant that extracts structured habit data from diary entries.

IMPORTANT RULES:
1. Extract ONLY information that is explicitly mentioned or strongly implied in the text.
2. If a value is not mentioned, use null (for nullable fields) or the appropriate default.
3. Do NOT hallucinate or assume values that aren't supported by the text.
4. For boolean-like fields (0/1), only set to 1 if the activity is clearly mentioned as done.
5. Preserve the original language when generating the diary summary.

The habit schema you need to fill:
{schema_description}

User's diary entry:
{input_text}

Extract the habit data according to the schema. Be conservative - when in doubt, use null or 0."""


class HabitExtractor(IHabitExtractor):
    """Extracts structured habit data from free-form text using LLM."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
    
    async def extract(
        self,
        text: str,
        schema: HabitSchema,
        language: str = "ru",
    ) -> dict[str, Any]:
        """
        Extract habit data from free-form text.
        
        Args:
            text: The raw user input (text or transcription).
            schema: The user's habit schema configuration.
            language: Expected language of the input.
            
        Returns:
            Dictionary with extracted field values.
        """
        try:
            # Build dynamic schema
            extraction_model = build_habit_extraction_schema(schema)
            
            # Create schema description for prompt
            schema_desc = self._build_schema_description(schema)
            
            # Create prompt
            prompt = ChatPromptTemplate.from_template(HABIT_EXTRACTION_PROMPT)
            
            # Get structured output model
            structured_llm = self._llm.with_structured_output(extraction_model)
            
            # Create chain
            chain = prompt | structured_llm
            
            # Execute
            result = await chain.ainvoke({
                "schema_description": schema_desc,
                "input_text": text,
            })
            
            # Convert to dict
            extracted = result.model_dump()
            
            logger.info(
                "Habit extraction completed",
                fields_extracted=len(extracted),
                language=language,
            )
            
            return extracted
            
        except Exception as e:
            logger.error("Habit extraction failed", error=str(e))
            raise ExtractionError(
                f"Failed to extract habits: {e}",
                user_message="Failed to process your entry. Please try again.",
            )
    
    def _build_schema_description(self, schema: HabitSchema) -> str:
        """Build human-readable schema description for prompt."""
        lines = []
        for name, config in schema.fields.items():
            if name == "raw_record":
                continue  # Skip raw_record in description
            
            type_str = config.type
            if isinstance(type_str, list):
                type_str = " | ".join(type_str)
            
            constraints = []
            if config.minimum is not None:
                constraints.append(f"min={config.minimum}")
            if config.maximum is not None:
                constraints.append(f"max={config.maximum}")
            
            constraint_str = f" ({', '.join(constraints)})" if constraints else ""
            
            lines.append(
                f"- {name} ({type_str}{constraint_str}): {config.description}"
            )
        
        return "\n".join(lines)
```

### 8.4 Dream Extractor Implementation

```python
# src/services/llm/extractors/dream_extractor.py

from typing import Any
from langchain_core.prompts import ChatPromptTemplate

from src.services.llm.client import LLMClient
from src.services.llm.schemas import DreamExtraction
from src.services.llm.interfaces import IDreamExtractor
from src.core.exceptions import ExtractionError
from src.core.logging import get_logger

logger = get_logger(__name__)

DREAM_EXTRACTION_PROMPT = """You are an assistant that analyzes dream descriptions.

Extract the following information from the dream description:
1. mood: The overall emotional tone (e.g., 'happy', 'scary', 'peaceful', 'anxious', 'confused', 'neutral')
2. is_lucid: Whether the dreamer was aware they were dreaming (true/false/null if unclear)
3. tags: Key themes, objects, or elements (up to 5 tags)
4. summary: A brief 1-2 sentence summary in the SAME LANGUAGE as the input

Dream description:
{input_text}

Be conservative with your analysis. Only mark as lucid if explicitly stated or strongly implied."""


class DreamExtractor(IDreamExtractor):
    """Extracts metadata from dream descriptions."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
    
    async def extract(
        self,
        text: str,
        language: str = "ru",
    ) -> dict[str, Any]:
        """Extract dream metadata from text."""
        try:
            prompt = ChatPromptTemplate.from_template(DREAM_EXTRACTION_PROMPT)
            structured_llm = self._llm.with_structured_output(DreamExtraction)
            chain = prompt | structured_llm
            
            result = await chain.ainvoke({"input_text": text})
            extracted = result.model_dump()
            
            logger.info("Dream extraction completed", tags=extracted.get("tags", []))
            return extracted
            
        except Exception as e:
            logger.error("Dream extraction failed", error=str(e))
            raise ExtractionError(f"Failed to extract dream metadata: {e}")
```

### 8.5 Thought Tagger Implementation

```python
# src/services/llm/extractors/thought_extractor.py

from typing import Any
from langchain_core.prompts import ChatPromptTemplate

from src.services.llm.client import LLMClient
from src.services.llm.schemas import ThoughtExtraction
from src.services.llm.interfaces import IThoughtTagger
from src.core.exceptions import ExtractionError
from src.core.logging import get_logger

logger = get_logger(__name__)

THOUGHT_TAGGING_PROMPT = """You are an assistant that categorizes and tags notes and thoughts.

Analyze the following thought/note and provide:
1. tags: Up to 5 relevant keywords or topics
2. category: One of 'idea', 'reminder', 'observation', 'question', or 'other'

Thought/note:
{input_text}

Keep tags concise (1-2 words each). Choose the most appropriate single category."""


class ThoughtTagger(IThoughtTagger):
    """Tags and categorizes thoughts/notes."""
    
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client
    
    async def tag(
        self,
        text: str,
        language: str = "ru",
    ) -> dict[str, Any]:
        """Tag a thought with categories and keywords."""
        try:
            prompt = ChatPromptTemplate.from_template(THOUGHT_TAGGING_PROMPT)
            structured_llm = self._llm.with_structured_output(ThoughtExtraction)
            chain = prompt | structured_llm
            
            result = await chain.ainvoke({"input_text": text})
            extracted = result.model_dump()
            
            logger.info(
                "Thought tagging completed",
                category=extracted.get("category"),
                tag_count=len(extracted.get("tags", [])),
            )
            return extracted
            
        except Exception as e:
            logger.error("Thought tagging failed", error=str(e))
            raise ExtractionError(f"Failed to tag thought: {e}")
```

---

## 9. Telegram Bot Implementation

### 9.1 Bot Initialization

```python
# src/services/telegram/bot.py

from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from src.config.settings import get_settings
from src.services.telegram.handlers import (
    start,
    habits,
    dream,
    thought,
    reflect,
    config,
    help as help_handler,
    callbacks,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    settings = get_settings()
    
    # Build application
    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .build()
    )
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start.handle_start))
    application.add_handler(CommandHandler("habits", habits.handle_habits))
    application.add_handler(CommandHandler("dream", dream.handle_dream))
    application.add_handler(CommandHandler("thought", thought.handle_thought))
    application.add_handler(CommandHandler("reflect", reflect.handle_reflect))
    application.add_handler(CommandHandler("config", config.handle_config))
    application.add_handler(CommandHandler("help", help_handler.handle_help))
    
    # Register callback query handler for inline buttons
    application.add_handler(
        CallbackQueryHandler(callbacks.handle_callback)
    )
    
    # Register message handlers for text and voice
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            habits.handle_text_message,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.VOICE | filters.AUDIO,
            habits.handle_voice_message,
        )
    )
    
    # Error handler
    application.add_error_handler(error_handler)
    
    logger.info("Bot application created and configured")
    return application


async def error_handler(update: Update, context) -> None:
    """Handle uncaught errors."""
    logger.error(
        "Unhandled error in bot",
        error=str(context.error),
        update=update.to_dict() if update else None,
    )
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred. Please try again later."
        )


async def setup_webhook(application: Application, webhook_url: str) -> None:
    """Configure webhook for the bot."""
    settings = get_settings()
    
    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=settings.telegram_webhook_secret or None,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Webhook configured", url=webhook_url)
```

### 9.2 Keyboard Builders

```python
# src/services/telegram/keyboards.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.models.enums import CallbackAction


def build_date_selection_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Build keyboard for date selection."""
    if language == "ru":
        buttons = [
            [
                InlineKeyboardButton("📅 Сегодня", callback_data=CallbackAction.DATE_TODAY),
                InlineKeyboardButton("📅 Вчера", callback_data=CallbackAction.DATE_YESTERDAY),
            ],
            [
                InlineKeyboardButton("📆 Другая дата", callback_data=CallbackAction.DATE_CUSTOM),
            ],
            [
                InlineKeyboardButton("❌ Отмена", callback_data=CallbackAction.NAV_CANCEL),
            ],
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton("📅 Today", callback_data=CallbackAction.DATE_TODAY),
                InlineKeyboardButton("📅 Yesterday", callback_data=CallbackAction.DATE_YESTERDAY),
            ],
            [
                InlineKeyboardButton("📆 Other date", callback_data=CallbackAction.DATE_CUSTOM),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data=CallbackAction.NAV_CANCEL),
            ],
        ]
    
    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Build keyboard for confirmation."""
    if language == "ru":
        buttons = [
            [
                InlineKeyboardButton("✅ Да, сохранить", callback_data=CallbackAction.CONFIRM_YES),
                InlineKeyboardButton("❌ Нет", callback_data=CallbackAction.CONFIRM_NO),
            ],
            [
                InlineKeyboardButton("✏️ Редактировать", callback_data=CallbackAction.CONFIRM_EDIT),
            ],
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton("✅ Yes, save", callback_data=CallbackAction.CONFIRM_YES),
                InlineKeyboardButton("❌ No", callback_data=CallbackAction.CONFIRM_NO),
            ],
            [
                InlineKeyboardButton("✏️ Edit", callback_data=CallbackAction.CONFIRM_EDIT),
            ],
        ]
    
    return InlineKeyboardMarkup(buttons)


def build_main_menu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Build main menu keyboard."""
    if language == "ru":
        buttons = [
            [
                InlineKeyboardButton("📝 Привычки", callback_data=CallbackAction.ENTRY_HABITS),
                InlineKeyboardButton("💤 Сон", callback_data=CallbackAction.ENTRY_DREAM),
            ],
            [
                InlineKeyboardButton("💡 Мысль", callback_data=CallbackAction.ENTRY_THOUGHT),
                InlineKeyboardButton("🪞 Рефлексия", callback_data=CallbackAction.ENTRY_REFLECT),
            ],
            [
                InlineKeyboardButton("⚙️ Настройки", callback_data=CallbackAction.CONFIG_SHEET),
            ],
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton("📝 Habits", callback_data=CallbackAction.ENTRY_HABITS),
                InlineKeyboardButton("💤 Dream", callback_data=CallbackAction.ENTRY_DREAM),
            ],
            [
                InlineKeyboardButton("💡 Thought", callback_data=CallbackAction.ENTRY_THOUGHT),
                InlineKeyboardButton("🪞 Reflect", callback_data=CallbackAction.ENTRY_REFLECT),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data=CallbackAction.CONFIG_SHEET),
            ],
        ]
    
    return InlineKeyboardMarkup(buttons)


def build_config_menu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Build configuration menu keyboard."""
    if language == "ru":
        buttons = [
            [
                InlineKeyboardButton(
                    "📊 Google Sheet", callback_data=CallbackAction.CONFIG_SHEET
                ),
            ],
            [
                InlineKeyboardButton(
                    "📋 Привычки", callback_data=CallbackAction.CONFIG_HABITS
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ Вопросы", callback_data=CallbackAction.CONFIG_QUESTIONS
                ),
            ],
            [
                InlineKeyboardButton("◀️ Назад", callback_data=CallbackAction.NAV_BACK),
            ],
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    "📊 Google Sheet", callback_data=CallbackAction.CONFIG_SHEET
                ),
            ],
            [
                InlineKeyboardButton(
                    "📋 Habits", callback_data=CallbackAction.CONFIG_HABITS
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ Questions", callback_data=CallbackAction.CONFIG_QUESTIONS
                ),
            ],
            [
                InlineKeyboardButton("◀️ Back", callback_data=CallbackAction.NAV_BACK),
            ],
        ]
    
    return InlineKeyboardMarkup(buttons)
```

### 9.3 Habits Handler

```python
# src/services/telegram/handlers/habits.py

import json
from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from src.services.storage.firestore.user_repo import UserRepository
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.storage.sheets.habits_sheet import HabitsSheetService
from src.services.storage.sheets.client import SheetsClient
from src.services.llm.client import LLMClient
from src.services.llm.extractors.habit_extractor import HabitExtractor
from src.services.transcription.whisper import WhisperClient
from src.services.telegram.keyboards import (
    build_date_selection_keyboard,
    build_confirmation_keyboard,
)
from src.models.session import ConversationState, SessionData
from src.models.entry import HabitEntry
from src.models.enums import InputType
from src.config.constants import MESSAGES_RU, MESSAGES_EN, HABITS_SHEET_COLUMNS
from src.core.exceptions import SheetNotConfiguredError
from src.core.logging import get_logger

logger = get_logger(__name__)

# Initialize services (in production, use dependency injection)
user_repo = UserRepository()
session_repo = SessionRepository()
llm_client = LLMClient()
habit_extractor = HabitExtractor(llm_client)
whisper_client = WhisperClient()


def get_messages(language: str) -> dict:
    """Get messages dictionary for language."""
    return MESSAGES_RU if language == "ru" else MESSAGES_EN


async def handle_habits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /habits command."""
    user_id = update.effective_user.id
    logger.info("Habits command received", user_id=user_id)
    
    # Get or create user profile
    user = await user_repo.get_by_telegram_id(user_id)
    if not user:
        await update.message.reply_text(
            "Please run /start first to set up your profile."
        )
        return
    
    messages = get_messages(user.language)
    
    # Check if sheet is configured
    if not user.sheet_id:
        await update.message.reply_text(messages["sheet_not_configured"])
        return
    
    # Set session state
    session = await session_repo.get_or_create(user_id)
    session.state = ConversationState.HABITS_AWAITING_DATE
    await session_repo.save(session)
    
    # Ask for date
    await update.message.reply_text(
        messages["select_date"],
        reply_markup=build_date_selection_keyboard(user.language),
    )


async def handle_date_selection(
    user_id: int,
    selected_date: date,
    context: ContextTypes.DEFAULT_TYPE,
    message,
) -> None:
    """Handle date selection for habits."""
    user = await user_repo.get_by_telegram_id(user_id)
    messages = get_messages(user.language)
    
    # Update session with selected date
    session = await session_repo.get(user_id)
    session.selected_date = selected_date
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    await session_repo.save(session)
    
    # Ask for content
    date_str = selected_date.isoformat()
    await message.reply_text(
        messages["describe_day"].format(date=date_str)
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text message based on session state."""
    user_id = update.effective_user.id
    text = update.message.text
    
    session = await session_repo.get(user_id)
    if not session:
        return
    
    if session.state == ConversationState.HABITS_AWAITING_CONTENT:
        await process_habit_content(
            user_id=user_id,
            content=text,
            input_type=InputType.TEXT,
            update=update,
            context=context,
        )
    elif session.state == ConversationState.HABITS_AWAITING_DATE:
        # Try to parse date from text
        from src.utils.date_parser import parse_date_ru
        parsed_date = parse_date_ru(text)
        if parsed_date:
            await handle_date_selection(
                user_id, parsed_date, context, update.message
            )
        else:
            await update.message.reply_text(
                "Не удалось распознать дату. Выберите из предложенных вариантов."
            )


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice message."""
    user_id = update.effective_user.id
    
    session = await session_repo.get(user_id)
    if not session or session.state != ConversationState.HABITS_AWAITING_CONTENT:
        return
    
    user = await user_repo.get_by_telegram_id(user_id)
    messages = get_messages(user.language)
    
    # Send processing message
    processing_msg = await update.message.reply_text(messages["processing"])
    
    try:
        # Download voice file
        voice = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        
        # Transcribe
        result = await whisper_client.transcribe(
            audio_data=bytes(audio_bytes),
            language_hint=user.language,
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Process transcribed content
        await process_habit_content(
            user_id=user_id,
            content=result.text,
            input_type=InputType.VOICE,
            update=update,
            context=context,
        )
        
    except Exception as e:
        logger.error("Voice processing failed", error=str(e), user_id=user_id)
        await processing_msg.edit_text(messages["error_occurred"])


async def process_habit_content(
    user_id: int,
    content: str,
    input_type: InputType,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Process habit content (text or transcribed voice)."""
    user = await user_repo.get_by_telegram_id(user_id)
    session = await session_repo.get(user_id)
    messages = get_messages(user.language)
    
    # Send processing message
    processing_msg = await update.message.reply_text(messages["processing"])
    
    try:
        # Extract structured data
        extracted = await habit_extractor.extract(
            text=content,
            schema=user.habit_schema,
            language=user.language,
        )
        
        # Build entry
        entry_data = {
            "date": session.selected_date,
            "raw_record": content,  # Always original text
            "diary": extracted.get("diary"),
            "extra_fields": {
                k: v for k, v in extracted.items()
                if k not in ("diary",)
            },
            "input_type": input_type.value,
        }
        
        # Store pending entry in session
        session.pending_entry = entry_data
        session.state = ConversationState.HABITS_AWAITING_CONFIRMATION
        await session_repo.save(session)
        
        # Delete processing message
        await processing_msg.delete()
        
        # Show extracted data for confirmation
        display_data = {
            "date": session.selected_date.isoformat(),
            **extracted,
            "raw_record": content[:200] + "..." if len(content) > 200 else content,
        }
        
        json_str = json.dumps(display_data, ensure_ascii=False, indent=2)
        await update.message.reply_text(
            messages["confirm_entry"].format(json_data=json_str),
            reply_markup=build_confirmation_keyboard(user.language),
            parse_mode="Markdown",
        )
        
    except Exception as e:
        logger.error("Habit processing failed", error=str(e), user_id=user_id)
        await processing_msg.edit_text(messages["error_occurred"])


async def confirm_habit_entry(
    user_id: int,
    message,
) -> None:
    """Save confirmed habit entry to Google Sheets."""
    user = await user_repo.get_by_telegram_id(user_id)
    session = await session_repo.get(user_id)
    messages = get_messages(user.language)
    
    if not session.pending_entry:
        await message.reply_text(messages["error_occurred"])
        return
    
    try:
        # Build entry from pending data
        entry = HabitEntry(
            date=session.pending_entry["date"],
            raw_record=session.pending_entry["raw_record"],
            diary=session.pending_entry.get("diary"),
            extra_fields=session.pending_entry.get("extra_fields", {}),
            input_type=session.pending_entry.get("input_type", "text"),
        )
        
        # Save to Google Sheets
        sheets_client = SheetsClient()
        habits_service = HabitsSheetService(sheets_client)
        
        await habits_service.append_entry(
            sheet_id=user.sheet_id,
            entry=entry,
            field_order=HABITS_SHEET_COLUMNS,
        )
        
        # Reset session
        session.reset()
        await session_repo.save(session)
        
        await message.reply_text(messages["saved_success"])
        
    except Exception as e:
        logger.error("Failed to save habit entry", error=str(e), user_id=user_id)
        await message.reply_text(messages["error_occurred"])


async def cancel_habit_entry(user_id: int, message) -> None:
    """Cancel pending habit entry."""
    user = await user_repo.get_by_telegram_id(user_id)
    messages = get_messages(user.language)
    
    session = await session_repo.get(user_id)
    session.reset()
    await session_repo.save(session)
    
    await message.reply_text(messages["cancelled"])
```

### 9.4 Callback Handler

```python
# src/services/telegram/handlers/callbacks.py

from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from src.models.enums import CallbackAction
from src.services.telegram.handlers import habits, dream, thought
from src.services.storage.firestore.session_repo import SessionRepository
from src.core.logging import get_logger

logger = get_logger(__name__)

session_repo = SessionRepository()


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button callbacks."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    user_id = update.effective_user.id
    
    logger.debug("Callback received", action=action, user_id=user_id)
    
    # Date selection
    if action == CallbackAction.DATE_TODAY:
        await habits.handle_date_selection(
            user_id=user_id,
            selected_date=date.today(),
            context=context,
            message=query.message,
        )
    
    elif action == CallbackAction.DATE_YESTERDAY:
        await habits.handle_date_selection(
            user_id=user_id,
            selected_date=date.today() - timedelta(days=1),
            context=context,
            message=query.message,
        )
    
    elif action == CallbackAction.DATE_CUSTOM:
        await query.message.reply_text(
            "Введите дату в формате YYYY-MM-DD или напишите словами (например, 'позавчера'):"
        )
    
    # Confirmation
    elif action == CallbackAction.CONFIRM_YES:
        await habits.confirm_habit_entry(user_id, query.message)
    
    elif action == CallbackAction.CONFIRM_NO:
        await habits.cancel_habit_entry(user_id, query.message)
    
    elif action == CallbackAction.CONFIRM_EDIT:
        await query.message.reply_text(
            "Функция редактирования в разработке. Пока можно отменить и начать заново."
        )
    
    # Navigation
    elif action == CallbackAction.NAV_CANCEL:
        session = await session_repo.get(user_id)
        if session:
            session.reset()
            await session_repo.save(session)
        await query.message.reply_text("❌ Отменено.")
    
    # Entry type selection from main menu
    elif action == CallbackAction.ENTRY_HABITS:
        # Simulate /habits command
        await habits.handle_habits(update, context)
    
    elif action == CallbackAction.ENTRY_DREAM:
        await dream.handle_dream(update, context)
    
    elif action == CallbackAction.ENTRY_THOUGHT:
        await thought.handle_thought(update, context)
    
    else:
        logger.warning("Unknown callback action", action=action)
```

### 9.5 Start Handler

```python
# src/services/telegram/handlers/start.py

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from src.services.storage.firestore.user_repo import UserRepository
from src.services.storage.firestore.session_repo import SessionRepository
from src.models.user import UserProfile
from src.models.session import SessionData, ConversationState
from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.services.telegram.keyboards import build_main_menu_keyboard
from src.core.logging import get_logger

logger = get_logger(__name__)

user_repo = UserRepository()
session_repo = SessionRepository()

WELCOME_MESSAGE_RU = """👋 Привет, {name}!

Я помогу тебе вести дневник и отслеживать привычки.

**Что я умею:**
• 📝 **/habits** — записать привычки и дневник за день
• 💤 **/dream** — записать сон
• 💡 **/thought** — быстро записать мысль или идею
• 🪞 **/reflect** — ответить на вопросы для рефлексии
• ⚙️ **/config** — настроить Google Sheet и привычки

**Для начала работы** нужно подключить Google Sheet:
1. Создайте новую Google таблицу
2. Откройте доступ для email: `bot-service@your-project.iam.gserviceaccount.com`
3. Отправьте мне ссылку на таблицу

Выберите действие или используйте команды:
"""

WELCOME_MESSAGE_EN = """👋 Hello, {name}!

I'll help you keep a diary and track habits.

**What I can do:**
• 📝 **/habits** — record habits and diary for the day
• 💤 **/dream** — log a dream
• 💡 **/thought** — quickly save a thought or idea
• 🪞 **/reflect** — answer reflection questions
• ⚙️ **/config** — configure Google Sheet and habits

**To get started**, you need to connect a Google Sheet:
1. Create a new Google spreadsheet
2. Share it with: `bot-service@your-project.iam.gserviceaccount.com`
3. Send me the link to the spreadsheet

Choose an action or use commands:
"""


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - onboarding and welcome."""
    user = update.effective_user
    user_id = user.id
    
    logger.info(
        "Start command received",
        user_id=user_id,
        username=user.username,
    )
    
    # Check if user exists
    existing_user = await user_repo.get_by_telegram_id(user_id)
    
    if existing_user:
        # Existing user - show welcome back message
        language = existing_user.language
        messages = WELCOME_MESSAGE_RU if language == "ru" else WELCOME_MESSAGE_EN
        
        await update.message.reply_text(
            messages.format(name=user.first_name),
            reply_markup=build_main_menu_keyboard(language),
            parse_mode="Markdown",
        )
    else:
        # New user - create profile
        new_user = UserProfile(
            telegram_user_id=user_id,
            telegram_username=user.username,
            habit_schema=DEFAULT_HABIT_SCHEMA,
            language="ru",  # Default to Russian
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        await user_repo.create(new_user)
        
        # Create session for onboarding
        session = SessionData(
            user_id=user_id,
            state=ConversationState.ONBOARDING_SHEET_SETUP,
        )
        await session_repo.save(session)
        
        logger.info("New user created", user_id=user_id)
        
        await update.message.reply_text(
            WELCOME_MESSAGE_RU.format(name=user.first_name),
            reply_markup=build_main_menu_keyboard("ru"),
            parse_mode="Markdown",
        )
```

---

## 10. Speech-to-Text Integration

### 10.1 Whisper Client

```python
# src/services/transcription/whisper.py

import httpx
from typing import Optional

from src.services.transcription.interfaces import ITranscriber, TranscriptionResult
from src.config.settings import get_settings
from src.core.exceptions import TranscriptionError
from src.core.logging import get_logger

logger = get_logger(__name__)


class WhisperClient(ITranscriber):
    """OpenAI Whisper API client for speech-to-text."""
    
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.whisper_model
        self._base_url = "https://api.openai.com/v1/audio/transcriptions"
    
    async def transcribe(
        self,
        audio_data: bytes,
        format: str = "ogg",
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text using Whisper API.
        
        Args:
            audio_data: Raw audio bytes
            format: Audio format (ogg, mp3, wav, etc.)
            language_hint: Expected language (ISO code)
            
        Returns:
            TranscriptionResult with transcribed text
        """
        try:
            # Prepare form data
            files = {
                "file": (f"audio.{format}", audio_data, f"audio/{format}"),
            }
            data = {
                "model": self._model,
            }
            
            if language_hint:
                data["language"] = language_hint
            
            # Make request
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self._base_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    files=files,
                    data=data,
                )
                
                response.raise_for_status()
                result = response.json()
            
            text = result.get("text", "").strip()
            
            logger.info(
                "Transcription completed",
                text_length=len(text),
                language=language_hint,
            )
            
            return TranscriptionResult(
                text=text,
                language=language_hint,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Whisper API error",
                status_code=e.response.status_code,
                detail=e.response.text,
            )
            raise TranscriptionError(
                f"Transcription API error: {e.response.status_code}",
                user_message="Failed to transcribe audio. Please try again.",
            )
        except Exception as e:
            logger.error("Transcription failed", error=str(e))
            raise TranscriptionError(
                f"Transcription failed: {e}",
                user_message="Failed to transcribe audio. Please try again.",
            )
    
    async def transcribe_file(
        self,
        file_path: str,
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio from file path."""
        with open(file_path, "rb") as f:
            audio_data = f.read()
        
        # Detect format from extension
        format = file_path.split(".")[-1].lower()
        
        return await self.transcribe(
            audio_data=audio_data,
            format=format,
            language_hint=language_hint,
        )
```

### 10.2 Audio Utilities

```python
# src/services/transcription/audio_utils.py

import tempfile
from pathlib import Path
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


def get_audio_format(file_name: str) -> str:
    """Extract audio format from file name."""
    extension = Path(file_name).suffix.lower().lstrip(".")
    
    # Map Telegram formats to standard formats
    format_map = {
        "oga": "ogg",
        "opus": "ogg",
    }
    
    return format_map.get(extension, extension or "ogg")


async def convert_audio_format(
    audio_data: bytes,
    source_format: str,
    target_format: str = "mp3",
) -> bytes:
    """
    Convert audio between formats using ffmpeg.
    
    Note: Requires ffmpeg to be installed.
    """
    try:
        import subprocess
        
        with tempfile.NamedTemporaryFile(
            suffix=f".{source_format}", delete=False
        ) as src_file:
            src_file.write(audio_data)
            src_path = src_file.name
        
        dst_path = src_path.replace(f".{source_format}", f".{target_format}")
        
        # Run ffmpeg conversion
        subprocess.run(
            ["ffmpeg", "-i", src_path, "-y", dst_path],
            capture_output=True,
            check=True,
        )
        
        with open(dst_path, "rb") as f:
            converted = f.read()
        
        # Cleanup
        Path(src_path).unlink(missing_ok=True)
        Path(dst_path).unlink(missing_ok=True)
        
        logger.debug(
            "Audio converted",
            source_format=source_format,
            target_format=target_format,
        )
        
        return converted
        
    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg conversion failed", error=e.stderr)
        raise
    except FileNotFoundError:
        logger.error("FFmpeg not found")
        raise RuntimeError("FFmpeg is required for audio conversion")
```

---

## 11. Error Handling & Resilience

### 11.1 Retry Decorator

```python
# src/utils/retry.py

import asyncio
from functools import wraps
from typing import Type, Tuple, Callable, Any

from src.core.logging import get_logger

logger = get_logger(__name__)


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Async retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            "Max retry attempts reached",
                            func=func.__name__,
                            attempts=max_attempts,
                            error=str(e),
                        )
                        raise
                    
                    logger.warning(
                        "Retry attempt",
                        func=func.__name__,
                        attempt=attempt,
                        next_delay=current_delay,
                        error=str(e),
                    )
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator
```

### 11.2 Circuit Breaker

```python
# src/utils/circuit_breaker.py

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external services.
    
    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: type = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def __aenter__(self):
        async with self._lock:
            await self._check_state()
            
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open"
                )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            if exc_type is None:
                await self._on_success()
            elif issubclass(exc_type, self.expected_exception):
                await self._on_failure()
        
        return False  # Don't suppress exceptions
    
    async def _check_state(self):
        """Check and potentially update circuit state."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker half-open",
                    name=self.name,
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True
        
        return datetime.utcnow() > (
            self._last_failure_time + timedelta(seconds=self.recovery_timeout)
        )
    
    async def _on_success(self):
        """Handle successful operation."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failures = 0
            logger.info("Circuit breaker closed", name=self.name)
        elif self._state == CircuitState.CLOSED:
            self._failures = 0
    
    async def _on_failure(self):
        """Handle failed operation."""
        self._failures += 1
        self._last_failure_time = datetime.utcnow()
        
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker re-opened",
                name=self.name,
            )
        elif self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker opened",
                name=self.name,
                failures=self._failures,
            )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
```

---

## 12. Deployment Guide

### 12.1 Dockerfile

```dockerfile
# Dockerfile

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 12.2 Main Application Entry Point

```python
# src/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from telegram import Update

from src.config.settings import get_settings
from src.core.logging import setup_logging, get_logger
from src.core.dependencies import verify_telegram_webhook
from src.services.telegram.bot import create_bot_application, setup_webhook
from src.services.storage.firestore.client import close_firestore_client

logger = get_logger(__name__)

# Global bot application instance
bot_application = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global bot_application
    
    # Startup
    setup_logging()
    logger.info("Starting application")
    
    settings = get_settings()
    bot_application = create_bot_application()
    
    # Initialize bot
    await bot_application.initialize()
    await bot_application.start()
    
    # Setup webhook if URL is configured
    if settings.telegram_webhook_url:
        await setup_webhook(bot_application, settings.telegram_webhook_url)
    
    logger.info("Application started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    if bot_application:
        await bot_application.stop()
        await bot_application.shutdown()
    
    await close_firestore_client()
    
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Habits Diary Bot",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy"}


@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    _: bool = Depends(verify_telegram_webhook),
):
    """Handle Telegram webhook updates."""
    global bot_application
    
    if not bot_application:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        data = await request.json()
        update = Update.de_json(data, bot_application.bot)
        
        await bot_application.process_update(update)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error("Webhook processing error", error=str(e))
        # Return 200 to prevent Telegram from retrying
        return {"ok": False, "error": str(e)}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Habits Diary Bot",
        "version": "2.0.0",
        "status": "running",
    }
```

### 12.3 Cloud Build Configuration

```yaml
# cloudbuild.yaml

steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/habits-diary-bot:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/habits-diary-bot:latest'
      - '.'

  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/habits-diary-bot:$COMMIT_SHA'
  
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/habits-diary-bot:latest'

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'habits-diary-bot'
      - '--image'
      - 'gcr.io/$PROJECT_ID/habits-diary-bot:$COMMIT_SHA'
      - '--region'
      - 'europe-west1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--set-secrets'
      - 'TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,OPENROUTER_API_KEY=openrouter-api-key:latest,OPENAI_API_KEY=openai-api-key:latest'
      - '--set-env-vars'
      - 'GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=europe-west1'
      - '--min-instances'
      - '0'
      - '--max-instances'
      - '3'
      - '--memory'
      - '512Mi'
      - '--cpu'
      - '1'
      - '--timeout'
      - '300'

images:
  - 'gcr.io/$PROJECT_ID/habits-diary-bot:$COMMIT_SHA'
  - 'gcr.io/$PROJECT_ID/habits-diary-bot:latest'

options:
  logging: CLOUD_LOGGING_ONLY
```

### 12.4 Requirements

```
# requirements.txt

# Web framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Telegram
python-telegram-bot>=20.7

# LLM
langchain>=0.1.0
langchain-openai>=0.0.5
openai>=1.6.0

# HTTP client
httpx>=0.25.0

# Google Cloud
google-cloud-firestore>=2.13.0
google-cloud-secret-manager>=2.16.0
google-api-python-client>=2.108.0
google-auth>=2.23.0

# Data validation
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Logging
structlog>=23.2.0

# Utilities
python-dateutil>=2.8.2

# Testing (dev only)
# pytest>=7.4.0
# pytest-asyncio>=0.21.0
# pytest-cov>=4.1.0
```

### 12.5 Environment Variables

```bash
# .env.example

# Application
DEBUG=false
LOG_LEVEL=INFO

# Google Cloud
GCP_PROJECT_ID=your-project-id
GCP_REGION=europe-west1

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_WEBHOOK_URL=https://your-service-url.run.app/webhook
TELEGRAM_WEBHOOK_SECRET=your-webhook-secret

# OpenRouter / LLM
OPENROUTER_API_KEY=your-openrouter-key
LLM_MODEL=anthropic/claude-3-5-sonnet
LLM_TEMPERATURE=0.1

# OpenAI (for Whisper)
OPENAI_API_KEY=your-openai-key

# Firestore
FIRESTORE_COLLECTION_USERS=users
FIRESTORE_COLLECTION_SESSIONS=sessions

# Session
SESSION_TTL_MINUTES=60
```

---

## 13. Testing Strategy

### 13.1 Test Configuration

```python
# tests/conftest.py

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.models.user import UserProfile, HabitSchema
from src.models.session import SessionData, ConversationState
from src.config.constants import DEFAULT_HABIT_SCHEMA


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_user() -> UserProfile:
    """Create sample user profile for testing."""
    return UserProfile(
        telegram_user_id=12345,
        telegram_username="testuser",
        sheet_id="test-sheet-id",
        habit_schema=DEFAULT_HABIT_SCHEMA,
        language="ru",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        onboarding_completed=True,
    )


@pytest.fixture
def sample_session() -> SessionData:
    """Create sample session for testing."""
    return SessionData(
        user_id=12345,
        state=ConversationState.IDLE,
    )


@pytest.fixture
def mock_user_repo():
    """Create mock user repository."""
    repo = AsyncMock()
    repo.get_by_telegram_id = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_session_repo():
    """Create mock session repository."""
    repo = AsyncMock()
    repo.get = AsyncMock()
    repo.save = AsyncMock()
    repo.get_or_create = AsyncMock()
    return repo


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = MagicMock()
    client.with_structured_output = MagicMock()
    return client


@pytest.fixture
def sample_diary_text_ru() -> str:
    """Sample Russian diary entry."""
    return """
    Сегодня был хороший день. Утром сделал зарядку, потом пошел в зал на тренировку.
    Вечером выпил пару бокалов вина. Настроение отличное, 5 из 5. 
    День был довольно важный - закрыл большой проект на работе.
    """


@pytest.fixture
def expected_extraction() -> dict:
    """Expected extraction result for sample diary text."""
    return {
        "morning_exercises": 1,
        "training": 1,
        "alcohol": 2,
        "mood": 5,
        "sex": 0,
        "masturbation": 0,
        "day_importance": 3,
        "diary": "Утренняя зарядка, тренировка в зале, немного вина вечером. Закрыл важный проект.",
    }
```

### 13.2 Unit Tests for Extractors

```python
# tests/unit/test_extractors.py (continued)

class TestHabitSchemaBuilder:
    """Tests for dynamic schema building."""
    
    def test_builds_correct_fields(self):
        """Should build schema with all non-raw_record fields."""
        schema = build_habit_extraction_schema(DEFAULT_HABIT_SCHEMA)
        
        # Check that raw_record is excluded
        assert "raw_record" not in schema.model_fields
        
        # Check expected fields exist
        expected_fields = [
            "morning_exercises", "training", "alcohol", "mood",
            "sex", "masturbation", "day_importance", "diary"
        ]
        for field in expected_fields:
            assert field in schema.model_fields
    
    def test_nullable_fields_are_optional(self):
        """Should make nullable fields optional."""
        schema = build_habit_extraction_schema(DEFAULT_HABIT_SCHEMA)
        
        # mood is defined as ["integer", "null"]
        mood_field = schema.model_fields.get("mood")
        assert mood_field is not None
        # Check that None is allowed
        assert mood_field.is_required() is False
    
    def test_excludes_diary_when_requested(self):
        """Should exclude diary field when include_diary=False."""
        schema = build_habit_extraction_schema(
            DEFAULT_HABIT_SCHEMA,
            include_diary=False
        )
        
        assert "diary" not in schema.model_fields


class TestHabitExtractor:
    """Tests for habit extraction."""
    
    @pytest.fixture
    def extractor(self, mock_llm_client):
        """Create extractor with mocked LLM client."""
        return HabitExtractor(mock_llm_client)
    
    @pytest.mark.asyncio
    async def test_extracts_habits_from_text(
        self,
        extractor,
        mock_llm_client,
        sample_diary_text_ru,
        expected_extraction,
    ):
        """Should extract structured habits from diary text."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.model_dump.return_value = expected_extraction
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_response)
        
        mock_structured = MagicMock()
        mock_structured.__or__ = MagicMock(return_value=mock_chain)
        mock_llm_client.with_structured_output.return_value = mock_structured
        
        # Execute
        result = await extractor.extract(
            text=sample_diary_text_ru,
            schema=DEFAULT_HABIT_SCHEMA,
            language="ru",
        )
        
        # Verify
        assert result["morning_exercises"] == 1
        assert result["training"] == 1
        assert result["alcohol"] == 2
        assert result["mood"] == 5
    
    @pytest.mark.asyncio
    async def test_handles_extraction_error(
        self,
        extractor,
        mock_llm_client,
    ):
        """Should raise ExtractionError on LLM failure."""
        from src.core.exceptions import ExtractionError
        
        # Setup mock to raise exception
        mock_llm_client.with_structured_output.side_effect = Exception("LLM error")
        
        with pytest.raises(ExtractionError):
            await extractor.extract(
                text="test text",
                schema=DEFAULT_HABIT_SCHEMA,
            )
```

### 13.3 Unit Tests for Date Parser

```python
# tests/unit/test_date_parser.py

import pytest
from datetime import date, timedelta

from src.utils.date_parser import parse_date_ru, parse_date_en


class TestDateParserRussian:
    """Tests for Russian date parsing."""
    
    def test_parses_today(self):
        """Should parse 'сегодня' as today."""
        result = parse_date_ru("сегодня")
        assert result == date.today()
    
    def test_parses_yesterday(self):
        """Should parse 'вчера' as yesterday."""
        result = parse_date_ru("вчера")
        assert result == date.today() - timedelta(days=1)
    
    def test_parses_day_before_yesterday(self):
        """Should parse 'позавчера' as day before yesterday."""
        result = parse_date_ru("позавчера")
        assert result == date.today() - timedelta(days=2)
    
    def test_parses_iso_format(self):
        """Should parse ISO date format."""
        result = parse_date_ru("2024-01-15")
        assert result == date(2024, 1, 15)
    
    def test_parses_russian_format(self):
        """Should parse Russian date format DD.MM.YYYY."""
        result = parse_date_ru("15.01.2024")
        assert result == date(2024, 1, 15)
    
    def test_returns_none_for_invalid(self):
        """Should return None for unparseable text."""
        result = parse_date_ru("какой-то текст")
        assert result is None
    
    def test_handles_case_insensitive(self):
        """Should handle case variations."""
        assert parse_date_ru("СЕГОДНЯ") == date.today()
        assert parse_date_ru("Вчера") == date.today() - timedelta(days=1)


class TestDateParserEnglish:
    """Tests for English date parsing."""
    
    def test_parses_today(self):
        """Should parse 'today'."""
        result = parse_date_en("today")
        assert result == date.today()
    
    def test_parses_yesterday(self):
        """Should parse 'yesterday'."""
        result = parse_date_en("yesterday")
        assert result == date.today() - timedelta(days=1)
    
    def test_parses_days_ago(self):
        """Should parse 'X days ago' format."""
        result = parse_date_en("3 days ago")
        assert result == date.today() - timedelta(days=3)
```

### 13.4 Integration Tests

```python
# tests/integration/test_llm_integration.py

import pytest
import os

from src.services.llm.client import LLMClient
from src.services.llm.extractors.habit_extractor import HabitExtractor
from src.config.constants import DEFAULT_HABIT_SCHEMA


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)
class TestLLMIntegration:
    """Integration tests with real LLM API."""
    
    @pytest.fixture
    def llm_client(self):
        """Create real LLM client."""
        return LLMClient()
    
    @pytest.fixture
    def extractor(self, llm_client):
        """Create extractor with real LLM client."""
        return HabitExtractor(llm_client)
    
    @pytest.mark.asyncio
    async def test_extracts_habits_from_russian_text(self, extractor):
        """Should extract habits from Russian diary entry."""
        text = """
        Отличный день! Утром сделал зарядку и пробежку. 
        Вечером был на тренировке в зале. 
        Настроение хорошее, где-то на 4.
        Алкоголь не пил.
        """
        
        result = await extractor.extract(
            text=text,
            schema=DEFAULT_HABIT_SCHEMA,
            language="ru",
        )
        
        assert result["morning_exercises"] == 1
        assert result["training"] == 1
        assert result["alcohol"] == 0
        assert result["mood"] == 4
    
    @pytest.mark.asyncio
    async def test_handles_missing_information(self, extractor):
        """Should handle text with missing habit information."""
        text = "Просто обычный день, ничего особенного."
        
        result = await extractor.extract(
            text=text,
            schema=DEFAULT_HABIT_SCHEMA,
            language="ru",
        )
        
        # Should default to 0/null for unmentioned habits
        assert result["morning_exercises"] == 0
        assert result["training"] == 0
        assert result["mood"] is None  # nullable field
```

### 13.5 End-to-End Tests

```python
# tests/e2e/test_conversation_flows.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes

from src.services.telegram.handlers.habits import (
    handle_habits,
    handle_text_message,
    process_habit_content,
    confirm_habit_entry,
)
from src.models.session import ConversationState
from src.models.enums import InputType


def create_mock_update(
    user_id: int = 12345,
    text: str = "",
    username: str = "testuser",
) -> Update:
    """Create a mock Telegram Update object."""
    user = MagicMock(spec=User)
    user.id = user_id
    user.username = username
    user.first_name = "Test"
    
    chat = MagicMock(spec=Chat)
    chat.id = user_id
    
    message = MagicMock(spec=Message)
    message.text = text
    message.chat = chat
    message.from_user = user
    message.reply_text = AsyncMock()
    message.delete = AsyncMock()
    
    update = MagicMock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.message = message
    update.effective_message = message
    
    return update


@pytest.mark.e2e
class TestHabitsConversationFlow:
    """End-to-end tests for habits conversation flow."""
    
    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = MagicMock()
        return context
    
    @pytest.mark.asyncio
    async def test_complete_habits_flow(
        self,
        mock_context,
        sample_user,
        mock_user_repo,
        mock_session_repo,
    ):
        """Test complete flow: /habits -> date -> content -> confirm -> save."""
        user_id = sample_user.telegram_user_id
        
        # Setup mocks
        mock_user_repo.get_by_telegram_id.return_value = sample_user
        mock_session_repo.get_or_create.return_value = MagicMock(
            state=ConversationState.IDLE
        )
        
        with patch(
            "src.services.telegram.handlers.habits.user_repo",
            mock_user_repo
        ), patch(
            "src.services.telegram.handlers.habits.session_repo",
            mock_session_repo
        ):
            # Step 1: User sends /habits
            update = create_mock_update(user_id=user_id, text="/habits")
            await handle_habits(update, mock_context)
            
            # Verify date selection keyboard was shown
            update.message.reply_text.assert_called()
            call_kwargs = update.message.reply_text.call_args.kwargs
            assert "reply_markup" in call_kwargs
    
    @pytest.mark.asyncio
    async def test_handles_unconfigured_sheet(
        self,
        mock_context,
        sample_user,
        mock_user_repo,
        mock_session_repo,
    ):
        """Test that missing sheet configuration shows error."""
        # User without sheet configured
        sample_user.sheet_id = None
        
        mock_user_repo.get_by_telegram_id.return_value = sample_user
        
        with patch(
            "src.services.telegram.handlers.habits.user_repo",
            mock_user_repo
        ):
            update = create_mock_update(user_id=sample_user.telegram_user_id)
            await handle_habits(update, mock_context)
            
            # Should show sheet configuration message
            update.message.reply_text.assert_called()
            call_args = update.message.reply_text.call_args[0][0]
            assert "config" in call_args.lower() or "sheet" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_voice_message_flow(
        self,
        mock_context,
        sample_user,
        mock_user_repo,
        mock_session_repo,
    ):
        """Test voice message processing flow."""
        from src.models.session import SessionData
        from datetime import date
        
        user_id = sample_user.telegram_user_id
        session = SessionData(
            user_id=user_id,
            state=ConversationState.HABITS_AWAITING_CONTENT,
            selected_date=date.today(),
        )
        
        mock_user_repo.get_by_telegram_id.return_value = sample_user
        mock_session_repo.get.return_value = session
        
        # Create update with voice message
        update = create_mock_update(user_id=user_id)
        update.message.voice = MagicMock()
        update.message.voice.file_id = "test_file_id"
        update.message.text = None
        
        # Mock file download
        mock_file = AsyncMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=b"audio_data")
        mock_context.bot.get_file = AsyncMock(return_value=mock_file)
        
        # Mock transcription
        mock_transcription_result = MagicMock()
        mock_transcription_result.text = "Сегодня был хороший день"
        
        with patch(
            "src.services.telegram.handlers.habits.user_repo",
            mock_user_repo
        ), patch(
            "src.services.telegram.handlers.habits.session_repo",
            mock_session_repo
        ), patch(
            "src.services.telegram.handlers.habits.whisper_client"
        ) as mock_whisper:
            mock_whisper.transcribe = AsyncMock(return_value=mock_transcription_result)
            
            from src.services.telegram.handlers.habits import handle_voice_message
            await handle_voice_message(update, mock_context)
            
            # Verify transcription was called
            mock_whisper.transcribe.assert_called_once()
```

---

## 14. Security Considerations

### 14.1 Security Checklist

| Area | Requirement | Implementation |
|------|-------------|----------------|
| **Authentication** | Verify Telegram webhook requests | Secret token header validation |
| **Authorization** | Users can only access their own data | User ID validation in all handlers |
| **Secrets Management** | No hardcoded credentials | Google Secret Manager |
| **Data Privacy** | Sensitive data handling | GDPR-compliant data storage |
| **Input Validation** | Sanitize all user input | Pydantic validation |
| **Rate Limiting** | Prevent abuse | Per-user rate limits |
| **Logging** | Audit trail without PII | Structured logging with filtering |
| **HTTPS** | Encrypted communication | Cloud Run default TLS |
| **Sheet Access** | Minimal permissions | Read/write only to user's sheet |

### 14.2 Secrets Manager Integration

```python
# src/services/secrets/manager.py

from typing import Optional
from google.cloud import secretmanager
from functools import lru_cache

from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class SecretManager:
    """Google Cloud Secret Manager integration."""
    
    def __init__(self):
        settings = get_settings()
        self._project_id = settings.gcp_project_id
        self._client = None
    
    def _get_client(self) -> secretmanager.SecretManagerServiceClient:
        """Get or create Secret Manager client."""
        if self._client is None:
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client
    
    def get_secret(
        self,
        secret_id: str,
        version: str = "latest",
    ) -> Optional[str]:
        """
        Retrieve a secret from Secret Manager.
        
        Args:
            secret_id: The secret identifier
            version: Version to retrieve (default: "latest")
            
        Returns:
            The secret value as string, or None if not found
        """
        try:
            client = self._get_client()
            name = f"projects/{self._project_id}/secrets/{secret_id}/versions/{version}"
            
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.debug("Secret retrieved", secret_id=secret_id)
            return secret_value
            
        except Exception as e:
            logger.error(
                "Failed to retrieve secret",
                secret_id=secret_id,
                error=str(e),
            )
            return None
    
    def create_secret(
        self,
        secret_id: str,
        secret_value: str,
    ) -> bool:
        """Create a new secret."""
        try:
            client = self._get_client()
            parent = f"projects/{self._project_id}"
            
            # Create secret
            secret = client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            
            # Add secret version
            client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info("Secret created", secret_id=secret_id)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to create secret",
                secret_id=secret_id,
                error=str(e),
            )
            return False


@lru_cache()
def get_secret_manager() -> SecretManager:
    """Get cached Secret Manager instance."""
    return SecretManager()
```

### 14.3 Input Validation Utilities

```python
# src/utils/validators.py

import re
from typing import Optional
from urllib.parse import urlparse

from src.core.exceptions import ValidationError


def validate_google_sheet_url(url: str) -> str:
    """
    Validate and extract sheet ID from Google Sheets URL.
    
    Args:
        url: The Google Sheets URL
        
    Returns:
        The extracted sheet ID
        
    Raises:
        ValidationError: If URL is invalid
    """
    # Pattern for Google Sheets URLs
    patterns = [
        r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)",
        r"^([a-zA-Z0-9-_]{44})$",  # Direct sheet ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    
    raise ValidationError(
        "Invalid Google Sheets URL",
        user_message="Please provide a valid Google Sheets URL.",
    )


def validate_telegram_user_id(user_id: int) -> bool:
    """Validate Telegram user ID."""
    return isinstance(user_id, int) and user_id > 0


def sanitize_text_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user text input.
    
    Args:
        text: Raw user input
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Strip whitespace
    text = text.strip()
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    return text


def validate_habit_schema(schema: dict) -> bool:
    """
    Validate a habit schema configuration.
    
    Args:
        schema: The schema dictionary to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If schema is invalid
    """
    required_fields = ["type", "description"]
    valid_types = ["integer", "string", "boolean", "number"]
    
    for field_name, field_config in schema.items():
        # Check required keys
        for req in required_fields:
            if req not in field_config:
                raise ValidationError(
                    f"Field '{field_name}' missing required key '{req}'"
                )
        
        # Validate type
        field_type = field_config["type"]
        if isinstance(field_type, list):
            for t in field_type:
                if t not in valid_types + ["null"]:
                    raise ValidationError(
                        f"Invalid type '{t}' in field '{field_name}'"
                    )
        elif field_type not in valid_types:
            raise ValidationError(
                f"Invalid type '{field_type}' in field '{field_name}'"
            )
        
        # Validate min/max for numeric types
        if field_config.get("minimum") is not None:
            if not isinstance(field_config["minimum"], (int, float)):
                raise ValidationError(
                    f"Invalid minimum in field '{field_name}'"
                )
        
        if field_config.get("maximum") is not None:
            if not isinstance(field_config["maximum"], (int, float)):
                raise ValidationError(
                    f"Invalid maximum in field '{field_name}'"
                )
    
    return True
```

### 14.4 Rate Limiter

```python
# src/utils/rate_limiter.py

import time
from collections import defaultdict
from typing import Dict, Tuple
import asyncio

from src.core.exceptions import RateLimitError
from src.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for per-user request limiting.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 30,
        burst_size: int = 5,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        
        # user_id -> (tokens, last_refill_time)
        self._buckets: Dict[int, Tuple[float, float]] = defaultdict(
            lambda: (float(burst_size), time.time())
        )
        self._lock = asyncio.Lock()
    
    async def acquire(self, user_id: int) -> bool:
        """
        Attempt to acquire a token for the user.
        
        Args:
            user_id: The user's Telegram ID
            
        Returns:
            True if token acquired, False otherwise
            
        Raises:
            RateLimitError: If rate limit exceeded
        """
        async with self._lock:
            tokens, last_refill = self._buckets[user_id]
            
            # Refill tokens based on time elapsed
            now = time.time()
            elapsed = now - last_refill
            tokens = min(
                self.burst_size,
                tokens + (elapsed * self.refill_rate)
            )
            
            if tokens >= 1:
                # Consume a token
                self._buckets[user_id] = (tokens - 1, now)
                return True
            else:
                # Rate limited
                self._buckets[user_id] = (tokens, now)
                logger.warning(
                    "Rate limit exceeded",
                    user_id=user_id,
                    tokens_remaining=tokens,
                )
                raise RateLimitError()
    
    def reset(self, user_id: int) -> None:
        """Reset the rate limit for a user."""
        if user_id in self._buckets:
            del self._buckets[user_id]
    
    def cleanup_old_entries(self, max_age_seconds: int = 3600) -> int:
        """
        Remove entries older than max_age_seconds.
        
        Returns:
            Number of entries removed
        """
        now = time.time()
        to_remove = [
            user_id
            for user_id, (_, last_refill) in self._buckets.items()
            if now - last_refill > max_age_seconds
        ]
        
        for user_id in to_remove:
            del self._buckets[user_id]
        
        return len(to_remove)


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        from src.config.settings import get_settings
        settings = get_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_requests_per_minute
        )
    return _rate_limiter
```

---

## 15. Utilities

### 15.1 Date Parser

```python
# src/utils/date_parser.py

import re
from datetime import date, timedelta
from typing import Optional
from dateutil import parser as dateutil_parser

from src.core.logging import get_logger

logger = get_logger(__name__)

# Russian date keywords
RU_DATE_KEYWORDS = {
    "сегодня": 0,
    "вчера": 1,
    "позавчера": 2,
}

# English date keywords
EN_DATE_KEYWORDS = {
    "today": 0,
    "yesterday": 1,
    "day before yesterday": 2,
}


def parse_date_ru(text: str) -> Optional[date]:
    """
    Parse date from Russian text.
    
    Supports:
    - Keywords: сегодня, вчера, позавчера
    - ISO format: YYYY-MM-DD
    - Russian format: DD.MM.YYYY
    - Natural language (limited)
    """
    text = text.strip().lower()
    
    # Check keywords
    for keyword, days_ago in RU_DATE_KEYWORDS.items():
        if keyword in text:
            return date.today() - timedelta(days=days_ago)
    
    # Check "X дней назад" pattern
    days_ago_match = re.search(r"(\d+)\s*дн[яей]+\s*назад", text)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return date.today() - timedelta(days=days)
    
    # Try ISO format
    iso_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        try:
            return date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
            )
        except ValueError:
            pass
    
    # Try Russian format DD.MM.YYYY
    ru_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if ru_match:
        try:
            return date(
                int(ru_match.group(3)),
                int(ru_match.group(2)),
                int(ru_match.group(1)),
            )
        except ValueError:
            pass
    
    # Try dateutil parser as fallback
    try:
        parsed = dateutil_parser.parse(text, dayfirst=True)
        return parsed.date()
    except (ValueError, TypeError):
        pass
    
    return None


def parse_date_en(text: str) -> Optional[date]:
    """
    Parse date from English text.
    
    Supports:
    - Keywords: today, yesterday
    - ISO format: YYYY-MM-DD
    - "X days ago" pattern
    - Natural language via dateutil
    """
    text = text.strip().lower()
    
    # Check keywords
    for keyword, days_ago in EN_DATE_KEYWORDS.items():
        if keyword in text:
            return date.today() - timedelta(days=days_ago)
    
    # Check "X days ago" pattern
    days_ago_match = re.search(r"(\d+)\s*days?\s*ago", text)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return date.today() - timedelta(days=days)
    
    # Try ISO format
    iso_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        try:
            return date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
            )
        except ValueError:
            pass
    
    # Try dateutil parser
    try:
        parsed = dateutil_parser.parse(text)
        return parsed.date()
    except (ValueError, TypeError):
        pass
    
    return None


def parse_date(text: str, language: str = "ru") -> Optional[date]:
    """
    Parse date from text in specified language.
    
    Args:
        text: The text to parse
        language: Language code ("ru" or "en")
        
    Returns:
        Parsed date or None if parsing failed
    """
    if language == "ru":
        return parse_date_ru(text)
    else:
        return parse_date_en(text)
```

### 15.2 Output Formatters

```python
# src/utils/formatters.py

import json
from datetime import date, datetime
from typing import Any, Dict


def format_habit_entry_for_display(
    entry_data: Dict[str, Any],
    language: str = "ru",
) -> str:
    """
    Format habit entry data for display in Telegram message.
    
    Args:
        entry_data: Dictionary with habit entry data
        language: Language for labels
        
    Returns:
        Formatted string for display
    """
    # Labels for Russian
    labels_ru = {
        "date": "📅 Дата",
        "morning_exercises": "🏃 Зарядка",
        "training": "💪 Тренировка",
        "alcohol": "🍷 Алкоголь",
        "mood": "😊 Настроение",
        "sex": "❤️ Секс",
        "masturbation": "🔒 Мастурбация",
        "day_importance": "⭐ Важность дня",
        "diary": "📝 Дневник",
        "raw_record": "📄 Оригинал",
    }
    
    # Labels for English
    labels_en = {
        "date": "📅 Date",
        "morning_exercises": "🏃 Morning exercises",
        "training": "💪 Training",
        "alcohol": "🍷 Alcohol",
        "mood": "😊 Mood",
        "sex": "❤️ Sex",
        "masturbation": "🔒 Masturbation",
        "day_importance": "⭐ Day importance",
        "diary": "📝 Diary",
        "raw_record": "📄 Original",
    }
    
    labels = labels_ru if language == "ru" else labels_en
    
    lines = []
    for key, value in entry_data.items():
        label = labels.get(key, key)
        
        # Format value
        if value is None:
            formatted_value = "—"
        elif isinstance(value, bool):
            formatted_value = "✅" if value else "❌"
        elif isinstance(value, (int, float)):
            if key in ("morning_exercises", "training", "sex"):
                formatted_value = "✅" if value else "❌"
            else:
                formatted_value = str(value)
        elif isinstance(value, str):
            # Truncate long strings
            if len(value) > 100:
                formatted_value = value[:100] + "..."
            else:
                formatted_value = value
        else:
            formatted_value = str(value)
        
        lines.append(f"{label}: {formatted_value}")
    
    return "\n".join(lines)


def format_json_for_telegram(data: Dict[str, Any], max_length: int = 3000) -> str:
    """
    Format JSON data for display in Telegram message.
    
    Args:
        data: Dictionary to format
        max_length: Maximum message length
        
    Returns:
        Formatted JSON string wrapped in code block
    """
    # Custom encoder for dates
    def json_encoder(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    json_str = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
        default=json_encoder,
    )
    
    # Truncate if needed
    if len(json_str) > max_length - 20:  # Leave room for code block markers
        json_str = json_str[:max_length - 25] + "\n... (обрезано)"
    
    return f"```json\n{json_str}\n```"


def format_error_message(error: Exception, language: str = "ru") -> str:
    """Format error message for user display."""
    from src.core.exceptions import BotException
    
    if isinstance(error, BotException) and error.user_message:
        return error.user_message
    
    if language == "ru":
        return "⚠️ Произошла ошибка. Пожалуйста, попробуйте ещё раз."
    else:
        return "⚠️ An error occurred. Please try again."
```

---

## 16. Appendix

### 16.1 Complete API Reference

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/` | GET | Root endpoint, service info | None |
| `/health` | GET | Health check for Cloud Run | None |
| `/webhook` | POST | Telegram webhook handler | Telegram secret |

### 16.2 Telegram Bot Commands

| Command | Description | Flow States |
|---------|-------------|-------------|
| `/start` | Onboarding and welcome | ONBOARDING_* |
| `/habits` | Record daily habits | HABITS_* |
| `/dream` | Log a dream | DREAM_* |
| `/thought` | Quick note/thought | THOUGHT_* |
| `/reflect` | Answer reflection questions | REFLECT_* |
| `/config` | Bot configuration | CONFIG_* |
| `/help` | Show help message | None |

### 16.3 Firestore Collections Schema

**Collection: `users`**
```json
{
  "document_id": "tg_{telegram_user_id}",
  "telegram_user_id": 12345,
  "telegram_username": "username",
  "sheet_id": "1abc...",
  "sheet_url": "https://docs.google.com/...",
  "sheets_validated": true,
  "habit_schema": { /* HabitSchema */ },
  "custom_questions": [ /* CustomQuestion[] */ ],
  "language": "ru",
  "timezone": "Europe/Moscow",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "onboarding_completed": true
}
```

**Collection: `sessions`**
```json
{
  "document_id": "session_{user_id}",
  "user_id": 12345,
  "state": "habits_awaiting_content",
  "selected_date": "2024-01-15",
  "pending_entry": { /* entry data */ },
  "current_question_index": null,
  "reflection_answers": {},
  "temp_data": {},
  "last_activity": "2024-01-15T12:00:00Z",
  "expires_at": "2024-01-15T13:00:00Z"
}
```

### 16.4 Google Sheets Structure

**Tab: Habits**
| Column | Type | Description |
|--------|------|-------------|
| date | DATE | ISO date (YYYY-MM-DD) |
| morning_exercises | INTEGER | 0 or 1 |
| training | INTEGER | 0 or 1 |
| alcohol | INTEGER | 0-3 |
| mood | INTEGER/NULL | 1-5 or empty |
| sex | INTEGER | 0 or 1 |
| masturbation | INTEGER | Count |
| day_importance | INTEGER | 1-3 |
| raw_record | TEXT | Original user input |
| diary | TEXT | LLM summary |

**Tab: Dreams**
| Column | Type | Description |
|--------|------|-------------|
| timestamp | DATETIME | When recorded |
| date | DATE | Dream date |
| record | TEXT | Original description |
| mood | TEXT | Extracted mood |
| is_lucid | BOOLEAN | Lucid dream flag |
| tags | TEXT | Comma-separated tags |
| summary | TEXT | LLM summary |

**Tab: Thoughts**
| Column | Type | Description |
|--------|------|-------------|
| timestamp | DATETIME | When recorded |
| record | TEXT | Original thought |
| tags | TEXT | Comma-separated tags |
| category | TEXT | idea/reminder/etc. |

**Tab: Reflections**
| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Reflection date |
| {question_id_1} | TEXT | Answer to question 1 |
| {question_id_2} | TEXT | Answer to question 2 |
| ... | ... | ... |

---

## 17. Development Workflow

### 17.1 Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/habits-diary-bot.git
cd habits-diary-bot

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Run locally with ngrok for webhook testing
ngrok http 8080

# 6. Update TELEGRAM_WEBHOOK_URL in .env with ngrok URL

# 7. Run the application
uvicorn src.main:app --reload --port 8080

# 8. Register webhook (one-time)
python scripts/setup_webhook.py
```

### 17.2 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run integration tests (requires API keys)
pytest tests/integration/ -m integration

# Run e2e tests
pytest tests/e2e/ -m e2e
```

### 17.3 Deployment Checklist

- [ ] All tests passing
- [ ] Environment variables configured in Cloud Run
- [ ] Secrets stored in Secret Manager
- [ ] Service account has required permissions
- [ ] Webhook URL updated after deployment
- [ ] Health check endpoint responding
- [ ] Logging configured and visible in Cloud Logging

---

This technical documentation provides a comprehensive guide for implementing the Habits & Diary Telegram Bot 2.0. The modular architecture allows for easy extension and maintenance, while the separation of concerns ensures clean code organization.
