# Security Review — 2026-08-06

Full-codebase security review of the Habits & Diary Telegram bot, framed against the
12 common vulnerability classes for AI-assisted projects. Threat model assumption:
**the app stores users' private diaries**, so confidentiality of user content is the
primary asset, above availability or integrity.

Reviewed at commit `c6edd9f` on `main`.

**Status: SEC-1 through SEC-5 fixed 2026-08-06. SEC-6 through SEC-10 outstanding.**
One deployment action is still required — see [Outstanding actions](#outstanding-actions).

## Findings at a glance

| ID | Severity | Finding | Location | Status |
|----|----------|---------|----------|--------|
| SEC-1 | 🔴 Critical | Any user can bind another user's diary sheet | `src/services/telegram/handlers/config.py:185-252` | ✅ Fixed |
| SEC-2 | 🔴 Critical | Full reflection text written to production logs | `src/services/llm/extractors/reflection_extractor.py:46` | ✅ Fixed |
| SEC-3 | 🟠 Medium | 47 dependency advisories, no audit in CI | `pyproject.toml`, `.github/workflows/ci.yml` | ✅ Fixed |
| SEC-4 | 🟠 Medium | Diary content persists in expired session docs | `src/models/session.py:44-51` | ⚠️ Code fixed, TTL policy pending |
| SEC-5 | 🟠 Medium | Rate limiting is in-memory and per-instance | `src/core/rate_limit.py` | ✅ Fixed |
| SEC-6 | 🟡 Low | Timing-unsafe secret comparison | `src/core/dependencies.py:54,67` | Open |
| SEC-7 | 🟡 Low | Read-then-write race on habit rows | `src/services/telegram/handlers/habits.py:470-490` | Open |
| SEC-8 | 🟡 Low | Prompt injection via diary content | `src/services/llm/extractors/` | Open |
| SEC-9 | 🟡 Low | `.gcloudignore` un-ignores service account keys | `.gcloudignore` | Open |
| SEC-10 | 🟡 Low | Dead `src/secrets/` package excluded from image | `src/secrets/`, `.dockerignore` | Open |

## Outstanding actions

Things the code changes cannot do for you:

1. **Apply the Firestore session TTL policy** (SEC-4). Until this runs, abandoned
   sessions keep their diary content indefinitely:
   ```bash
   gcloud firestore fields ttls update expires_at --collection-group=sessions --enable-ttl --project="$GCP_PROJECT_ID"
   ```
2. **Purge captured reflection text from Cloud Logging** (SEC-2). The fix stops new
   writes; records already collected are still there.
3. **Check for pre-existing sheet hijacks** (SEC-1). The fix blocks new ones only:
   ```bash
   python scripts/audit_sheet_ownership.py
   ```
4. **Redeploy.** None of the fixes take effect until the service is redeployed.

---

## SEC-1 🔴 Any user can bind another user's diary sheet (IDOR)

**Where:** [`src/services/telegram/handlers/config.py:185-252`](../src/services/telegram/handlers/config.py)

`/config` accepts any spreadsheet ID or URL. The only validation performed is:

```python
await asyncio.wait_for(sheets_client.ensure_tabs(sheet_id), timeout=_SHEETS_TIMEOUT)
```

This checks whether **the shared service account** can write to the sheet — and it can,
for *every* user's sheet, because every user is instructed to grant Editor access to the
same service account (`config.py:135`). The check therefore succeeds for any sheet
belonging to any user of the bot.

There is no verification that the submitting Telegram user owns the sheet, and
`UserRepository` (`src/services/storage/firestore/user_repo.py`) enforces no uniqueness
constraint on `sheet_id` — two profiles can hold the same value.

**Attack path**

1. Attacker obtains a victim's sheet ID. Realistic sources: a shared Google Sheets link,
   a screenshot, a forwarded URL, or a sheet still set to "anyone with the link" (the bot
   *recommends* Restricted access but cannot enforce it).
2. Attacker sends the ID to `/config` from their own Telegram account. Validation passes.
3. Attacker reads the victim's entire diary via `/on_this_day`
   (`src/services/telegram/handlers/on_this_day.py:91`) and `/week_analysis`
   (`src/services/telegram/handlers/week_analysis.py:51`), covering habits, dreams,
   thoughts, and reflections.
4. Attacker also has write access to all four tabs.

The victim receives no notification at any point.

Sheet IDs are ~44 random characters and are not brute-forceable, so this requires a leaked
link. That is a low bar in practice, and the payoff is a complete private diary.

**Remediation (cheapest first)**

1. **Uniqueness check.** Before `profile.sheet_id = sheet_id` (`config.py:249`), query for
   another profile already holding that ID and refuse the bind if the owner differs.
   Requires a Firestore index on `sheet_id`.
2. **Ownership proof.** Write a random nonce into a cell of the submitted sheet and ask the
   user to read it back. Proves the submitter can actually see the sheet.
3. **Invert the trust model (preferred).** Have the bot *create* the spreadsheet in a
   bot-owned Drive folder and share it with the user. The bot then owns the user→sheet
   mapping and this entire vulnerability class disappears.

**Related architectural note:** a single service account holds Editor access to every
user's diary. Compromise of that identity, or of the Cloud Run instance, exposes all
diaries simultaneously. Options 3 above does not fix this on its own; consider whether
per-user OAuth is viable long term.

---

## SEC-2 🔴 Full reflection text written to production logs

**Where:** [`src/services/llm/extractors/reflection_extractor.py:46`](../src/services/llm/extractors/reflection_extractor.py)

```python
messages = [
    SystemMessage(content=REFLECTION_EXTRACTION_SYSTEM_PROMPT),
    HumanMessage(content=(... f"User reply:\n{raw_text}\n" ...)),
]
logger.info(messages)
```

The entire LangChain message list is logged, including the `HumanMessage` carrying
`raw_text` — the user's **complete raw reflection answers**, the most intimate content the
app handles.

`LOG_LEVEL` defaults to `INFO` (`src/config/settings.py:22`) and structlog is configured
with `make_filtering_bound_logger(INFO)`, so this is **active in production**. Records land
in Cloud Logging (30-day default retention), readable by anyone holding
`roles/logging.viewer` on the project. Per [`docs/analytics.md`](analytics.md), a sink may
forward log records to BigQuery, extending both retention and audience.

**Remediation**

- Delete the line, or mirror the correct pattern already used in
  `habit_extractor.py:130`, which logs only `text_length` and schema field names.
- Audit existing Cloud Logging buckets for already-captured reflection text and purge.
- Consider a structlog processor that drops or redacts any field carrying user content, so
  a future `logger.info(...)` cannot reintroduce this.

---

## SEC-3 🟠 Vulnerable dependencies, no audit in CI

`pip-audit` against the current `.venv` (run 2026-08-06) reports **47 advisories across 21
packages**:

`click`, `httplib2`, `idna`, `langchain`, `langchain-core`, `langchain-openai`,
`langgraph`, `langgraph-checkpoint`, `langgraph-sdk`, `langsmith`, `orjson`, `pip`,
`protobuf`, `pyasn1`, `pydantic-settings`, `pygments`, `pytest`, `python-dotenv`,
`requests`, `starlette`, `urllib3`

Highest counts: `pyasn1` (8), `starlette` (7), `langchain-core` (5), `urllib3` (4),
`langsmith` (4). `starlette` and `urllib3` sit directly in the request path.

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs ruff, mypy, and pytest but
has no dependency audit, so this drifts silently.

**Remediation**

- Add `uv run pip-audit` as a CI step.
- Bump the flagged packages and re-lock (`uv lock`).
- `pyproject.toml` uses open lower bounds (`>=`) throughout; `uv.lock` pins the actual
  resolution, so the audit + lock refresh is the control that matters.

**Reproduce:**

```bash
.venv/bin/pip-audit --progress-spinner off
```

---

## SEC-4 🟠 Diary content persists in expired session documents

**Where:** [`src/models/session.py:44-51`](../src/models/session.py),
[`src/services/storage/firestore/session_repo.py:29`](../src/services/storage/firestore/session_repo.py)

`SessionData.pending_entry`, `temp_data`, and `reflection_answers` hold raw diary text
mid-flow (e.g. `temp_data["existing_raw_record"]` at `habits.py:483`) and are persisted to
Firestore via `session.model_dump(mode="json")`.

Expiry is enforced **only in application code, only on read**: `get()` checks
`is_expired()` and deletes. There is no Firestore TTL policy — `firebase.json` configures
rules only. A user who abandons a session mid-entry and never returns leaves their
plaintext diary content in Firestore permanently.

**Remediation**

- Add a Firestore TTL policy on the `sessions` collection keyed on `expires_at`.
- Consider clearing `temp_data` / `pending_entry` on write once an entry reaches Sheets,
  rather than relying on `reset()` being called on every path.

---

## SEC-5 🟠 Rate limiting is in-memory and per-instance

**Where:** [`src/core/rate_limit.py`](../src/core/rate_limit.py), applied in
[`src/services/telegram/bot.py:239`](../src/services/telegram/bot.py)

`SlidingWindowRateLimiter` keeps counters in a process-local dict. State resets on every
cold start, and `scripts/deploy_cloud_run.sh` deploys with `--min-instances 0`, so cold
starts are frequent. `--max-instances 1` currently makes the limit effectively global, but
that coupling is incidental and breaks the moment the service scales.

`/reminders/dispatch` (`src/main.py:68`) has no rate limit at all. It is authenticated by a
shared secret, so this is not directly exploitable, but with the secret it also acts as a
user-enumeration oracle (`{"skipped": "no_profile"}` vs. other responses).

**Remediation:** move the limiter to Firestore or Redis if the service ever scales past one
instance; add a limiter to `/reminders/dispatch`.

---

## SEC-6 🟡 Timing-unsafe secret comparison

**Where:** [`src/core/dependencies.py:54`](../src/core/dependencies.py) and `:67`

```python
if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
if x_reminder_secret != settings.reminders_dispatch_secret:
```

Plain `!=` on secret material is theoretically timing-attackable. Practically very hard to
exploit across the internet against Cloud Run, but the fix is free: use
`hmac.compare_digest`.

---

## SEC-7 🟡 Read-then-write race on habit rows

**Where:** [`src/services/telegram/handlers/habits.py:470-490`](../src/services/telegram/handlers/habits.py)

`find_latest_habit_entry` → store `existing_row_index` in session → later update that row.
No locking or transaction spans the read and the write. Two concurrent confirmations for
the same date (double-tapped button, retried webhook) can duplicate a row or clobber one
write with another.

Impact is data integrity within a single user's own sheet — no privilege boundary is
crossed. Mitigated somewhat by the per-user rate limiter and Telegram's own update
delivery, but not eliminated.

**Remediation:** guard the confirm handler with an idempotency key (e.g. the callback
message ID) so a repeated confirmation is a no-op.

---

## SEC-8 🟡 Prompt injection via diary content

**Where:** `src/services/llm/extractors/habit_extractor.py:143-151`,
`reflection_extractor.py:35-45`, `src/services/llm/prompts/weekly_analysis.py`

User diary text is interpolated directly into LLM prompts. A crafted entry can attempt to
steer extraction or the weekly summary.

Blast radius is limited: output returns to the same user who wrote the input, and habit
extraction is constrained by a structured-output schema. Worth noting rather than urgent.

---

## SEC-9 🟡 `.gcloudignore` un-ignores service account keys

**Where:** [`.gcloudignore`](../.gcloudignore)

```
#!include:.gitignore
!src/secrets/*.json
```

This deliberately re-includes service account JSON keys in the Cloud Build upload context.
With `BUILD_STRATEGY=cloud`, any key file placed there is uploaded to the Cloud Build
staging GCS bucket. `.dockerignore` excludes `src/secrets/` so the key does not reach the
image — but it does leave the machine.

The deploy script now defaults to `SERVICE_ACCOUNT` / Workload Identity, so no key file
should exist at all. **Remediation:** drop the exception line.

---

## SEC-10 🟡 Dead `src/secrets/` package, excluded from the image

**Where:** [`src/secrets/manager.py`](../src/secrets/manager.py), [`.dockerignore`](../.dockerignore)

`get_secret_from_env` is imported nowhere in `src/` or `tests/`. Separately, `.dockerignore`
excludes the whole `src/secrets/` directory, so the Python package is absent from the built
image despite `COPY src ./src`. If anything ever imports it, the container breaks at
startup.

**Remediation:** delete the package, or narrow `.dockerignore` to `src/secrets/*.json`.

---

## Verified as correctly handled

Recording these so future reviews don't re-litigate them.

| # | Class | Status |
|---|-------|--------|
| 1 | Bruteforce / credential stuffing | **N/A** — no login surface; Telegram owns identity |
| 2 | Secret & API key leaks | **Good** — `.env` gitignored and never present in git history (verified with `git log --all --diff-filter=A` across all branches); sensitive keys bound from Secret Manager in `deploy_cloud_run.sh`; Workload Identity by default |
| 3 | IDOR | **See SEC-1.** Firestore access itself is correct — documents are keyed by `telegram_user_id` and users only ever read their own |
| 4 | Broken access control | **Good** — `is_admin_user` checks `ADMIN_TELEGRAM_IDS` server-side in `_ensure_admin`, and the broadcast callback re-checks independently at `admin.py:172` |
| 5 | SQL injection | **N/A** — Firestore + Sheets API, no SQL |
| 6 | Unverified webhooks | **Good** — `X-Telegram-Bot-Api-Secret-Token` verified on `/telegram/webhook`; `X-Reminder-Secret` verified on `/reminders/dispatch` |
| 7 | Vulnerable dependencies | **See SEC-3** |
| 8 | XSS / injection into rendered output | **Good** — `html.escape` applied to all interpolated values in Telegram HTML previews (`habits.py:269-325`). **Sheets formula injection blocked** via `ValueInputOption.raw` with regression coverage in `tests/test_sheets_security.py` |
| 9 | Misconfigured CORS | **N/A** — no CORS middleware, no browser frontend; only three endpoints exist (`/health`, `/telegram/webhook`, `/reminders/dispatch`) |
| 10 | Malicious file uploads | **Good** — voice only, size-capped against `FileSizeLimit.FILESIZE_DOWNLOAD`, held in memory, never written to disk, never re-served |
| 11 | Race conditions | **See SEC-7** — low impact, no privilege boundary crossed |
| 12 | Credentials in logs | **See SEC-2.** No tokens or API keys are logged anywhere; the issue is user content, not credentials |

Also verified: `firestore.rules` denies all direct client access; the container runs as
non-root (`Dockerfile`); external calls are timeout-bounded throughout.

## What was fixed — 2026-08-06

**SEC-1.** `UserRepository.find_by_sheet_id` added (Firestore equality query, in-memory
fallback). `handle_config_text` now refuses a sheet already bound to a different
`telegram_user_id`, and does so **before** `ensure_tabs`, which would otherwise create tabs
in the victim's sheet during the attempt. The lookup deliberately does *not* fall back to
the in-memory store on backend failure — an empty store would report "unclaimed" and let
the bind through, so it raises and the handler fails closed. Re-binding your own sheet is
still allowed. Covered by four tests in `tests/test_config_handler.py`, verified to fail
against the pre-fix code. `scripts/audit_sheet_ownership.py` detects hijacks that predate
the fix.

**SEC-2.** `logger.info(messages)` replaced with a metadata-only record (language,
question count, text length). The response log also stopped emitting `payload.keys()`,
which were the user's own reflection questions. Guarded by
`tests/test_llm_logging_redaction.py`, verified to fail against the pre-fix code.

**SEC-3.** All 47 advisories cleared — `pip-audit` now reports no known vulnerabilities.
Notable jumps: starlette 0.50 → 1.4.1, fastapi 0.122 → 0.141.1, langchain 1.1 → 1.3.14,
urllib3 2.5 → 2.7, pyasn1 0.6.1 → 0.6.4. `pip-audit` added to CI (without `--strict`,
which would fail on the unauditable local project package). Two now-redundant
`# type: ignore` comments removed. Ruff pinned `<0.15`: 0.16 enables ~20 rules by default
that flag ~280 pre-existing style issues unrelated to security — that cleanup belongs in
its own change.

**SEC-4.** `SessionRepository.save` now writes `expires_at` as a native datetime.
`model_dump(mode="json")` was serializing it to an ISO string, and **Firestore TTL policies
silently ignore documents whose TTL field is not a timestamp** — so the policy alone would
not have worked. Regression test in `tests/test_session_expiry.py`. The policy itself still
needs applying (see Outstanding actions).

**SEC-5.** `/reminders/dispatch` gained a per-user limiter
(`REMINDERS_DISPATCH_RATE_LIMIT_PER_MINUTE`, default 10/min), returning 429 before any
storage access. The in-process limiter's dependency on `--max-instances 1` is now documented
at both the limiter and the deploy-script call site, so scaling out can't silently weaken it.
Covered by `tests/test_dispatch_rate_limit.py`.

Verification after all changes: 84 tests pass, mypy clean across 73 files, ruff clean,
`pip-audit` clean, and the app boots and rejects unauthenticated webhook/dispatch requests
with 403 under the upgraded FastAPI/starlette.

## Remaining work

1. **SEC-6, SEC-9, SEC-10** — small cleanups, batch together.
2. **SEC-7, SEC-8** — revisit as usage grows.
3. **Ruff unpin** — drop the `<0.15` ceiling and clear the ~280 style findings separately.
