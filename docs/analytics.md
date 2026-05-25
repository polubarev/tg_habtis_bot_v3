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
export REGION=US                    # BigQuery dataset location
export DATASET=bot_analytics
export SINK_NAME=habits-bot-analytics
export SERVICE_NAME=habits-diary-bot

# 1. Create the destination dataset.
bq --location="${REGION}" mk --dataset \
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

## Sample queries

Replace `PROJECT.bot_analytics.run_googleapis_com_stdout` with your fully qualified
table name. Sinks use a daily-partitioned `_PARTITIONTIME` column — filter on it
for cheap queries.

### 1. Daily active users (last 30 days)

```sql
SELECT
  DATE(timestamp)              AS day,
  COUNT(DISTINCT jsonPayload.user_id) AS dau
FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND jsonPayload.event = "bot_event"
  AND jsonPayload.user_id IS NOT NULL
GROUP BY day
ORDER BY day;
```

### 2. WAU / MAU rollups

```sql
WITH base AS (
  SELECT DATE(timestamp) AS day, jsonPayload.user_id AS uid
  FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
  WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
    AND jsonPayload.event = "bot_event"
    AND jsonPayload.user_id IS NOT NULL
)
SELECT
  day,
  COUNT(DISTINCT IF(uid IS NOT NULL, uid, NULL)) AS dau,
  (SELECT COUNT(DISTINCT uid) FROM base b2
    WHERE b2.day BETWEEN DATE_SUB(base.day, INTERVAL 6 DAY) AND base.day) AS wau,
  (SELECT COUNT(DISTINCT uid) FROM base b3
    WHERE b3.day BETWEEN DATE_SUB(base.day, INTERVAL 29 DAY) AND base.day) AS mau
FROM base
GROUP BY day
ORDER BY day;
```

### 3. Feature usage breakdown

```sql
SELECT
  jsonPayload.name               AS feature,
  COUNT(*)                       AS invocations,
  COUNT(DISTINCT jsonPayload.user_id) AS unique_users
FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND jsonPayload.event = "bot_event"
  AND jsonPayload.name LIKE "command.%"
GROUP BY feature
ORDER BY invocations DESC;
```

### 4. New users per day (first time `/start` was seen)

```sql
WITH first_seen AS (
  SELECT jsonPayload.user_id AS uid, MIN(DATE(timestamp)) AS first_day
  FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
  WHERE jsonPayload.event = "bot_event"
    AND jsonPayload.user_id IS NOT NULL
  GROUP BY uid
)
SELECT first_day AS day, COUNT(*) AS new_users
FROM first_seen
GROUP BY day
ORDER BY day;
```

### 5. LLM latency and volume

```sql
SELECT
  DATE(timestamp)                AS day,
  jsonPayload.extractor          AS extractor,
  COUNT(*)                       AS calls,
  COUNTIF(jsonPayload.ok = false) AS failures,
  APPROX_QUANTILES(jsonPayload.latency_ms, 100)[OFFSET(50)] AS p50_ms,
  APPROX_QUANTILES(jsonPayload.latency_ms, 100)[OFFSET(95)] AS p95_ms,
  SUM(jsonPayload.tokens_in)     AS tokens_in,
  SUM(jsonPayload.tokens_out)    AS tokens_out
FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
  AND jsonPayload.event = "bot_event"
  AND jsonPayload.name = "llm.call"
GROUP BY day, extractor
ORDER BY day, extractor;
```

### 6. Voice transcription volume

```sql
SELECT
  DATE(timestamp) AS day,
  COUNT(*)        AS transcriptions,
  COUNTIF(jsonPayload.ok = false) AS failures,
  SUM(jsonPayload.audio_bytes) / 1e6 AS audio_megabytes
FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND jsonPayload.event = "bot_event"
  AND jsonPayload.name = "transcription.call"
GROUP BY day
ORDER BY day;
```

### 7. Retention: users active in week N+1 after first seen in week N

```sql
WITH first_week AS (
  SELECT jsonPayload.user_id AS uid,
         DATE_TRUNC(MIN(DATE(timestamp)), WEEK) AS cohort_week
  FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
  WHERE jsonPayload.event = "bot_event"
    AND jsonPayload.user_id IS NOT NULL
  GROUP BY uid
),
weekly_activity AS (
  SELECT DISTINCT
    jsonPayload.user_id AS uid,
    DATE_TRUNC(DATE(timestamp), WEEK) AS active_week
  FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
  WHERE jsonPayload.event = "bot_event"
    AND jsonPayload.user_id IS NOT NULL
)
SELECT
  first_week.cohort_week,
  DATE_DIFF(weekly_activity.active_week, first_week.cohort_week, WEEK) AS week_offset,
  COUNT(DISTINCT first_week.uid) AS active_users
FROM first_week
JOIN weekly_activity USING (uid)
GROUP BY cohort_week, week_offset
ORDER BY cohort_week, week_offset;
```

### 8. Error rate per feature

```sql
SELECT
  jsonPayload.name AS event,
  COUNTIF(jsonPayload.ok = false) AS failures,
  COUNT(*) AS total,
  SAFE_DIVIDE(COUNTIF(jsonPayload.ok = false), COUNT(*)) AS failure_rate
FROM `PROJECT.bot_analytics.run_googleapis_com_stdout`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND jsonPayload.event = "bot_event"
  AND jsonPayload.name IN ("llm.call", "transcription.call")
GROUP BY event;
```

## Wiring Looker Studio

1. https://lookerstudio.google.com → **Create → Data source → BigQuery**.
2. Pick the `bot_analytics` dataset and the `run_googleapis_com_stdout` table
   (or **Custom Query** with one of the SQL blocks above to pre-aggregate).
3. Type-check fields after connecting — `user_id`, `latency_ms`, token counts
   should be **Number**; `timestamp` should be **Date & Time**.
4. Add filter controls on `jsonPayload.name` and a date range on `timestamp`.

A "good enough" v1 dashboard: DAU/WAU/MAU time series, feature-usage bar chart,
new-users-per-day, and an LLM-latency / cost-tokens row. Add the retention
cohort heatmap once you have ~6 weeks of data.

## Local development

structlog renders human-readable lines locally (`debug=true`) and JSON in Cloud
Run, so `log_event` calls show up in your terminal during dev:

```
2026-05-24 17:35:00 [info     ] bot_event   name=command.habits user_id=12345
```

No additional setup needed — the sink is a no-op until events reach Cloud Run.
