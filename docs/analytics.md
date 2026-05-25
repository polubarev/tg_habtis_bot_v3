# Analytics: BigQuery + Looker Studio

Bot usage events are emitted as structured Cloud Run logs and sunk to BigQuery
for dashboards.

## Event shape

Every analytics event is a single `INFO` log record whose JSON payload always
contains `event: "bot_event"` and `name: "<dotted action>"`. Helper:

```python
from src.core.analytics import log_event
log_event("command.habits", user_id=update.effective_user.id)
```

Top-level fields you can rely on in BigQuery (under `jsonPayload`):

| field          | type   | notes                                                                  |
| -------------- | ------ | ---------------------------------------------------------------------- |
| `event`        | STRING | Always `"bot_event"`. The sink filter pivots on this.                  |
| `name`         | STRING | Dotted action label — see below.                                       |
| `user_id`      | INT64  | Telegram user id. NULL for system events.                              |
| `level`        | STRING | structlog level (`info`).                                              |
| `timestamp`    | STRING | structlog ISO timestamp (use `timestamp` column added by the sink too) |
| extra `props`  | varies | Each kwarg passed to `log_event` becomes its own column.               |

### Event catalogue

| `name`                  | extra props                                                            |
| ----------------------- | ---------------------------------------------------------------------- |
| `command.start`         | —                                                                      |
| `command.help`          | —                                                                      |
| `command.habits`        | —                                                                      |
| `command.dream`         | —                                                                      |
| `command.thought`       | —                                                                      |
| `command.reflect`       | —                                                                      |
| `command.week_analysis` | —                                                                      |
| `command.on_this_day`   | —                                                                      |
| `command.feedback`      | —                                                                      |
| `command.config`        | —                                                                      |
| `command.reset`         | —                                                                      |
| `command.reminders`     | —                                                                      |
| `command.language`      | —                                                                      |
| `command.habits_config` | —                                                                      |
| `command.reflect_config`| —                                                                      |
| `voice.received`        | `duration_s`, `file_size`                                              |
| `transcription.call`    | `model`, `latency_ms`, `audio_bytes`, `language`, `text_length`, `ok`, `error` |
| `llm.call`              | `extractor` (`habit`/`reflection`/`week_analysis`), `model`, `latency_ms`, `tokens_in`, `tokens_out`, `ok`, `error` |

Note: `tokens_in`/`tokens_out` are only populated for raw `ainvoke` calls
(reflection, week_analysis). `with_structured_output` strips usage metadata,
so habit-extraction rows have NULL tokens.

## One-time setup: Cloud Logging → BigQuery sink

Defaults below assume the Cloud Run service is named `habits-diary-bot` and
deploys to the same GCP project referenced by `gcp_project_id` in `.env`.

```bash
export PROJECT_ID=<your-gcp-project>
export BQ_LOCATION=US               # BigQuery dataset location
export DATASET=bot_analytics
export SINK_NAME=habits-bot-analytics
export SERVICE_NAME=habits-diary-bot

# 1. Create the destination dataset.
bq --location="${BQ_LOCATION}" mk --dataset \
   --description "Analytics events from ${SERVICE_NAME}" \
   "${PROJECT_ID}:${DATASET}"

# 2. Create the log sink. The filter keeps only our analytics events,
#    so unrelated stdout doesn't bloat the table.
gcloud logging sinks create "${SINK_NAME}" \
   "bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DATASET}" \
   --project "${PROJECT_ID}" \
   --log-filter="resource.type=\"cloud_run_revision\"
                 AND resource.labels.service_name=\"${SERVICE_NAME}\"
                 AND jsonPayload.event=\"bot_event\""

# 3. Grant the sink's writer identity permission to write to BigQuery.
WRITER=$(gcloud logging sinks describe "${SINK_NAME}" \
           --project "${PROJECT_ID}" --format='value(writerIdentity)')
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
   --member="${WRITER}" --role="roles/bigquery.dataEditor"
```

After the first event arrives, BigQuery auto-creates a table named
`run_googleapis_com_stdout` (or `run_googleapis_com_stderr`) under the dataset.
Schema columns appear lazily as new fields are emitted — re-run a representative
flow (`/habits`, `/reflect`, a voice message, `/week_analysis`) to populate every
column before building dashboards.

## Dashboard data sources

Run SQL in the BigQuery workspace:
[BigQuery query editor for `tg-bot-sso`](https://console.cloud.google.com/bigquery?project=tg-bot-sso&ws=!1m0).
In the Google Cloud Console, you can also open **BigQuery → SQL workspace**,
paste a query, replace `tg-bot-sso` if needed, and click **Run**.

Cloud Logging exports stdout logs into daily sharded tables like
`run_googleapis_com_stdout_20260525`. Use the wildcard table
`run_googleapis_com_stdout_*` and filter `_TABLE_SUFFIX` to keep scans small.
Do not name dashboard views with the `run_googleapis_com_stdout_` prefix:
BigQuery wildcard queries fail if the wildcard matches a view.

### Option A: Looker Studio custom queries

This is fastest for one-off dashboards: create one BigQuery data source per SQL
block below using **BigQuery → Custom Query**.

### Option B: BigQuery views, then normal Looker Studio tables

This is better for reusable dashboards. Create views once in BigQuery, then
connect Looker Studio to the views as regular tables. This avoids pasting custom
queries into Looker Studio and keeps the business logic versioned in BigQuery.

Create the base normalized view first:

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.analytics_events` AS
SELECT
  timestamp,
  DATE(timestamp) AS day,
  jsonPayload.event AS event_type,
  jsonPayload.name AS event_name,
  CAST(jsonPayload.user_id AS STRING) AS user_id,
  JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.extractor') AS extractor,
  JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.model') AS model,
  SAFE_CAST(JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.ok') AS BOOL) AS ok,
  JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.error') AS error,
  SAFE_CAST(JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.latency_ms') AS INT64) AS latency_ms,
  SAFE_CAST(JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.tokens_in') AS INT64) AS tokens_in,
  SAFE_CAST(JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.tokens_out') AS INT64) AS tokens_out,
  SAFE_CAST(JSON_VALUE(TO_JSON_STRING(jsonPayload), '$.audio_bytes') AS INT64) AS audio_bytes
FROM `tg-bot-sso.bot_analytics.run_googleapis_com_stdout_*`
WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 180 DAY))
  AND jsonPayload.event = 'bot_event';
```

Then either query `analytics_events` directly, or create the summary views below.

### 1. Daily overview

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.dashboard_daily_overview` AS
SELECT
  day,
  COUNT(*) AS events,
  COUNT(DISTINCT user_id) AS active_users,
  COUNT(DISTINCT IF(event_name LIKE 'command.%', user_id, NULL)) AS command_users,
  COUNTIF(event_name LIKE 'command.%') AS command_events,
  COUNTIF(event_name = 'llm.call') AS llm_calls,
  COUNTIF(event_name = 'transcription.call') AS transcription_calls
FROM `tg-bot-sso.bot_analytics.analytics_events`
GROUP BY day;
```

Good charts: scorecards for active users/events/LLM calls, and a time series for
daily active users.

### 2. Feature usage

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.dashboard_feature_usage` AS
SELECT
  day,
  REPLACE(event_name, 'command.', '') AS feature,
  COUNT(*) AS uses,
  COUNT(DISTINCT user_id) AS users
FROM `tg-bot-sso.bot_analytics.analytics_events`
WHERE event_name LIKE 'command.%'
GROUP BY day, feature;
```

Good charts: bar chart by feature, stacked time series by feature, table of
features sorted by `uses`.

### 3. User retention cohorts

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.dashboard_user_retention` AS
WITH user_days AS (
  SELECT DISTINCT user_id, day
  FROM `tg-bot-sso.bot_analytics.analytics_events`
  WHERE user_id IS NOT NULL
),
first_seen AS (
  SELECT user_id, MIN(day) AS first_day
  FROM user_days
  GROUP BY user_id
)
SELECT
  first_seen.first_day,
  DATE_DIFF(user_days.day, first_seen.first_day, DAY) AS days_since_first_seen,
  COUNT(DISTINCT user_days.user_id) AS retained_users
FROM user_days
JOIN first_seen USING (user_id)
WHERE DATE_DIFF(user_days.day, first_seen.first_day, DAY) BETWEEN 0 AND 30
GROUP BY first_day, days_since_first_seen;
```

Good charts: heatmap with `first_day` and `days_since_first_seen`, or a line
chart filtered to recent cohorts.

### 4. LLM performance

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.dashboard_llm_performance` AS
SELECT
  day,
  extractor,
  model,
  COUNT(*) AS calls,
  COUNTIF(ok = false) AS failures,
  SAFE_DIVIDE(COUNTIF(ok = false), COUNT(*)) AS failure_rate,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] AS p50_ms,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_ms,
  SUM(tokens_in) AS tokens_in,
  SUM(tokens_out) AS tokens_out
FROM `tg-bot-sso.bot_analytics.analytics_events`
WHERE event_name = 'llm.call'
GROUP BY day, extractor, model;
```

Good charts: p95 latency over time, failure-rate scorecard, token volume by
extractor.

### 5. Voice usage

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.dashboard_voice_usage` AS
SELECT
  day,
  COUNT(*) AS transcriptions,
  COUNTIF(ok = false) AS failures,
  SAFE_DIVIDE(COUNTIF(ok = false), COUNT(*)) AS failure_rate,
  SUM(audio_bytes) / 1000000 AS audio_mb,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] AS p50_ms,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] AS p95_ms
FROM `tg-bot-sso.bot_analytics.analytics_events`
WHERE event_name = 'transcription.call'
GROUP BY day;
```

Good charts: daily transcriptions, audio MB, and p95 transcription latency.

### 6. Power users

```sql
CREATE OR REPLACE VIEW `tg-bot-sso.bot_analytics.dashboard_power_users` AS
SELECT
  user_id,
  COUNT(*) AS total_events,
  COUNTIF(event_name LIKE 'command.%') AS command_events,
  COUNT(DISTINCT day) AS active_days,
  MIN(day) AS first_seen,
  MAX(day) AS last_seen
FROM `tg-bot-sso.bot_analytics.analytics_events`
WHERE user_id IS NOT NULL
GROUP BY user_id;
```

Good charts: table sorted by active days, table sorted by total events, and a
scorecard for users active on at least three days.

## Wiring Looker Studio

1. Go to [Looker Studio](https://lookerstudio.google.com/reporting/create) →
   **Create → Report**.
2. Add data source → **BigQuery**.
3. Preferred: choose `tg-bot-sso` → `bot_analytics` → one of the
   `dashboard_*` views. Alternative: choose **Custom Query** and paste one of
   the SQL blocks above without the `CREATE OR REPLACE VIEW ... AS` line.
4. Type-check fields after connecting: `user_id` is text, counts/latencies/tokens
   are numbers, and `day` / `timestamp` are dates.
5. Add a report-level date range control using `day`, and optional filter
   controls for `feature`, `extractor`, and `model`.

A useful v1 dashboard layout:

1. Scorecards: active users, total events, command events, LLM calls, voice calls.
2. Time series: DAU from `dashboard_daily_overview`.
3. Feature section: bar chart and stacked trend from `dashboard_feature_usage`.
4. Reliability section: LLM and voice failure rates plus p95 latency.
5. Retention section: cohort heatmap from `dashboard_user_retention`.
6. User table: `dashboard_power_users` sorted by `active_days`.

## Local development

structlog renders human-readable lines locally (`debug=true`) and JSON in Cloud
Run, so `log_event` calls show up in your terminal during dev:

```
2026-05-24 17:35:00 [info     ] bot_event   name=command.habits user_id=12345
```

No additional setup needed — the sink is a no-op until events reach Cloud Run.
