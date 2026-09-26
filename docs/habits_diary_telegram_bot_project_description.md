# Habits & Diary Telegram Bot – Project Description

## 1. Overview

**Working name:** Habits & Diary Telegram Bot 2.0  
**Owner:** Igor  
**Platform:** Telegram Bot, deployed on Google Cloud Run (Python)

The project is a Telegram bot that helps users keep a daily diary and track habits using both text and audio messages. The bot uses an LLM (via OpenRouter + LangChain with structured output) to extract structured habit data from free-form descriptions and saves:

- **raw_record** – the original text (from text input or speech transcription); never modified by the LLM.  
- **diary** – the complete original diary text when enabled, without AI editing; new entries match `raw_record`.

All data (habits, diary, dreams, thoughts, answers to custom questions) is stored in a user-defined **Google Sheet**. The bot is optimized for Russian-speaking users but should work with other languages as well.

The system is designed to be:

- **Modular and clean** – easy to extend with new commands, schemas, and storage.  
- **On-demand and cost-efficient** – deployed on Cloud Run with scale-to-zero.  
- **Configurable per user** – habits, questions, and Google Sheet are user-specific.

---

## 2. Core Use Cases

1. **Daily habits + diary**  
   - User runs `/habits`.  
   - Chooses a date (e.g., "today", "yesterday", or a specific date).  
   - Sends a free-form description as text or voice.  
   - System transcribes voice (if needed), preserves the combined text in `raw_record` and, when enabled, `diary`, and uses the LLM only to extract configured habit values.
   - Bot shows extracted JSON and asks for confirmation.  
   - On confirmation, data is appended to the user’s Google Sheet.

2. **Dream logging**  
   - Command `/dream` or inline button (e.g., "💤 Dream").  
   - User sends text/voice about a dream.  
   - The bot stores the raw dream text plus optional LLM-derived metadata (mood, tags, lucid/non-lucid) into a separate **Dreams** sheet/tab.

3. **Thoughts / quick notes**  
   - Command `/thought` or button (e.g., "💡 Thought").  
   - User sends a short message (text/voice) with an idea or thought.  
   - Bot appends it to a **Thoughts** sheet/tab with timestamp and optional tags.

4. **Custom reflection questions**  
   - User defines their own questions (e.g., "What am I grateful for today?").  
   - With a command like `/reflect`, the bot asks these questions (text UI or buttons).  
   - User answers in text or voice, and the answers are stored in a **Reflections** sheet/tab.

5. **User configuration & onboarding**  
   - `/start` guides the user through:  
     - Connecting their Google Sheet (URL/ID).  
     - Reviewing or accepting default habit config.  
     - Adding custom questions.  
   - Config can be updated any time via commands (e.g., `/config`, `/habits_config`, `/reflect_config`).

---

## 3. Habit Configuration & Schema

Each user has a **habit configuration** that defines which fields the LLM should extract. The config is represented as a JSON-like schema. Example of a current configuration for one user:

```json
{
  "morning_exercises": {
    "type": "integer",
    "description": "Whether the person did morning exercises or not. 0 = no, 1 = yes."
  },
  "training": {
    "type": "integer",
    "description": "Whether the person did any training or workout during the day. 0 = no, 1 = yes."
  },
  "alcohol": {
    "type": "integer",
    "minimum": 0,
    "maximum": 3,
    "description": "Alcohol consumption level from 0 to 3."
  },
  "mood": {
    "type": ["integer", "null"],
    "minimum": 1,
    "maximum": 5,
    "description": "Mood level on a scale from 1 to 5, where 1 is very bad and 5 is very good. If the person did not explicitly mention a mood level, set this value to null."
  },
  "sex": {
    "type": "integer",
    "description": "Whether the person had sex. 0 = no, 1 = yes."
  },
  "masturbation": {
    "type": "integer",
    "description": "Number of times the person masturbated."
  },
  "diary": {
    "type": "string",
    "description": "Full original diary text, preserved exactly without AI editing."
  },
  "day_importance": {
    "type": "integer",
    "minimum": 1,
    "maximum": 3,
    "description": "A subjective rating of the day's importance on a scale from 1 (not important) to 3 (very important)."
  },
  "raw_record": {
    "type": "string",
    "description": "The original text description of the day, taken directly from the user input or speech transcription, without any modification by the LLM."
  }
}
```

Notes:

- `raw_record` is **always** the original content, either:  
  - text message from the user, or  
  - transcription result from the speech-to-text API.  
- `diary` equals `raw_record` for new entries when enabled; users can disable the diary field.
- The schema can be extended or edited by the user in a future config UI.

---

## 4. Data Storage in Google Sheets

Each user defines or confirms a Google Sheet where data will be stored. Recommended structure (tabs):

1. **Habits**
   - Columns (example):
     - `date` (ISO date)  
     - `morning_exercises`  
     - `training`  
     - `alcohol`  
     - `mood`  
     - `sex`  
     - `masturbation`  
     - `day_importance`  
     - `raw_record`  
     - `diary`

2. **Dreams**
   - Columns: `timestamp`, `date`, `record`, `mood`, `lucid`, `tags`, etc.

3. **Thoughts**
   - Columns: `timestamp`, `record`, `tags`.

4. **Reflections**
   - Columns: `date`, one column per custom question ID or stable name.

5. **Config (optional)**
   - Can store per-user configuration and schema if needed, but in most cases a separate backend store (Firestore) is more convenient.

The bot must validate the sheet structure on first use and create missing tabs/columns where appropriate (with user confirmation for destructive/large changes).

---

## 5. Tech Stack & Integrations

- **Language & runtime:** Python  
- **Deployment:** Google Cloud Run (containerized, scale-to-zero for on-demand usage).  
- **Messaging platform:** Telegram Bot API (webhook mode).
- **LLM:** OpenRouter + LangChain  
  - LangChain used for:
    - Prompt construction based on the user’s current schema.  
    - Enforcing **structured output** (Pydantic / JSON schema) so that the LLM responses map cleanly to fields like `morning_exercises`, `alcohol`, `mood`, `raw_record`, etc.  
- **Transcription (speech-to-text):**  
  - Any reliable API provider (e.g. Whisper API, Google Cloud Speech-to-Text).  
  - Must support Russian well, as most users will be Russian speakers.  
  - Output of STT is stored in `raw_record` (or `raw_dream`, `raw_thought` for other flows).
- **Storage:**  
  - Google Sheets API for main user data.  
  - Optional Firestore/Datastore for user config and session state.
- **Secrets & configuration:**  
  - Google Secret Manager for API keys, OpenRouter tokens, Telegram bot token, etc.

---

## 6. High-Level Architecture

1. **Telegram Webhook (Cloud Run service)**
   - Single HTTPS endpoint for Telegram updates.  
   - Verifies incoming requests.  
   - Parses messages and routes them to command handlers.

2. **Command & Dialog Layer**
   - Implements commands: `/start`, `/habits`, `/dream`, `/thought`, `/reflect`, `/reflect_config`, `/help`, etc.  
   - Handles multistep flows (date selection → data collection → confirmation → write to sheet).  
   - Stores minimal session state (e.g., expected next step, selected date) in a backend store.

3. **LLM Layer (OpenRouter + LangChain)**
   - Responsible for:  
     - Building prompts based on the user’s habit schema and language.  
     - Using structured output (Pydantic/JSON schema) for robust extraction.  
     - Validating and parsing model output.  
   - Separate templates for:  
     - Habit extraction for configured fields; diary text is preserved outside the LLM.
     - Dream metadata extraction.  
     - Thought tagging.  
     - Mapping answers to custom questions.

4. **Transcription Layer**
   - Downloads voice messages from Telegram.  
   - Sends audio to the chosen STT provider.  
   - Returns transcript (preferably with language info).  
   - Transcript is stored as `raw_record` / `record` before any LLM processing.

5. **Google Sheets Layer**
   - API wrapper functions like:  
     - `append_habit_entry(user_id, date, data)`  
     - `append_dream_entry(user_id, data)`  
     - `append_thought_entry(user_id, data)`  
     - `append_reflection_entry(user_id, date, answers)`  
   - Handles sheet/tab creation, column existence checks, and basic retries on failures.

6. **Config & User Profile Layer**
   - Stores per-user info:  
     - `telegram_user_id`  
     - `sheet_id`  
     - `habit_config` (JSON-like schema as above)  
     - `language`  
     - `custom_questions[]`
   - Used to dynamically generate prompts and determine where/how to write data.

---

## 7. Handling Hallucinations & Data Integrity

Because the LLM can hallucinate, especially for free-text fields, the design explicitly separates:

- **`raw_record`** – ground truth input from the user (text or transcription), never edited by the LLM.  
- **`diary`** – optional full copy of the combined original text for new entries, never rewritten by the LLM.

Additional measures:

- Use structured output with explicit types and ranges (via LangChain / JSON schema).  
- For fields like `mood`, `day_importance`, or `alcohol`, instruct the model to set `null` when info is not present.  
- Show a **confirmation step** in Telegram with the structured JSON so the user can say `Yes` / `No` or request manual corrections.

---

## 8. Example Interaction (Habits Flow)

A typical Russian-language interaction could look like this:

1. User: `/habits`  
2. Bot: «За какую дату ты хочешь записать привычки?»  
3. User: «Вчера»  
4. Bot: «Опиши свой день за 2025-11-27 текстом или голосом. Я сохраню оригинальный текст как `raw_record` и извлеку значения привычек.»  
5. User: отправляет голосовое сообщение.  
6. Bot:  
   - транскрибирует аудио → `raw_record`.  
   - запускает LLM для извлечения структуры на основе текущего конфига.  
   - отправляет пользователю данные привычек и полный `diary` (если включено).
7. Пользователь подтверждает → данные пишутся в Google Sheet.

---

This document is the working project description/spec for implementing the bot from scratch in a clean, modular way with OpenRouter + LangChain + structured output, a clear habit config schema, and original diary text kept outside LLM extraction.
