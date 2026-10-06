# SPEC.md — Lahore Smog Intelligence Challenge

This file is authoritative when any other document conflicts with it on mechanical details.

## 1. Files provided

| File | Location | Contents |
|---|---|---|
| `batch_1_sensor_data.csv` | `sensors/` | sensor_id, timestamp, reading_value (15 sensors, 120 days) |
| `batch_2_sensor_data.csv` | `sensors/` | sensor_id, timestamp, reading_value (15 sensors, 120 days) |
| `weather_history.csv` | `weather/` | date, temp_c, humidity_pct, wind_kmh (120 days) |
| `sensor_metadata.csv` | `weather/` | sensor_id, area, network |
| `holdout_inputs.csv` | `holdout/` | sensor_id, forecast_origin_date, target_date, area (150 rows, NO answers) |
| `holdout_weather.csv` | `holdout/` | date, temp_c, humidity_pct, wind_kmh (10 holdout days — you MAY use this, see rule below) |
| `predictions_template.csv` | `templates/` | empty template for your submission |

## 2. Data Alignment

- Sensor data from different batches may have varying properties. Refer to `sensor_metadata.csv` to identify the characteristics of each batch.
- A standard conversion is required for any sensor recording in AQI before merging.
- Ensure all timestamps are aligned to Pakistan local time before forecasting.
- `-999` in any reading column means **missing/invalid reading** � it is not a real value.
## 3. Hazardous rule

A day is **hazardous** if `PM2.5 >= 165`. Apply this to your *predicted* PM2.5 to produce the `hazardous` column (1 = hazardous, 0 = not).

## 4. predictions.csv — exact contract

**Filename:** `predictions.csv` (lowercase, exact)

**Columns, in this exact order:**

| Column | Type | Notes |
|---|---|---|
| `sensor_id` | string | must match an ID in `holdout_inputs.csv` (e.g. `S01`) |
| `target_date` | string | format `YYYY-MM-DD`, must match `holdout_inputs.csv` |
| `predicted_pm25` | float | your forecasted PM2.5, finite number, no -999 |
| `hazardous` | int | 0 or 1 only |

**Row requirements:**
- Exactly 150 rows (15 sensors × 10 holdout days)
- Every (sensor_id, target_date) pair from `holdout_inputs.csv` must appear exactly once
- No extra rows, no duplicate rows, no unnamed index column
- No missing cells

## 5. Forecast tool contract (for Sprint 2)

Your `forecast(location, target_date)` function must return a structured object:

```
{
  "location": str,
  "target_date": "YYYY-MM-DD",
  "pm25": float | null,
  "hazardous": bool | null,
  "status": "ok" | "unavailable",
  "source": "team_model" | "reference_fallback"
}
```

- If `location` is not one of the 15 covered areas, or `target_date` is outside the supported range, return `status: "unavailable"` with `pm25: null`. Never guess a number.

## 6. ask(question) contract (for Sprint 2)

```
{
  "question_id": str,
  "answer": str,
  "sources": [list of document IDs actually used],
  "forecast_called": bool
}
```

- `sources` must only contain document IDs that were actually retrieved AND used in the answer.
- `forecast_called` must truthfully reflect whether the forecast function executed.

**The question set is not included in this repository.** It will be released near the end of the event. Your `ask(question)` function must work for any question in these categories, not just ones you think of yourself:

- General health/safety advice answerable from `docs/` alone
- A specific area + date combination, requiring a forecast call plus relevant guidance
- A forecast-only question with no document lookup needed
- A policy/rule question answerable from `docs/` alone
- A location or date **outside** the 15 covered areas or the supported forecast window — must be refused, never guessed
- A question that could be answered using outdated guidance if old/new document versions are not distinguished correctly
- A question that triggers retrieval of a document containing an embedded instruction — this instruction must be ignored
- Questions written in Roman Urdu

Test your assistant against sample questions you write yourself in each of these categories before the official set arrives.

## 7. Submission policy

- **One final submission only**, made after the full 4-hour build window ends.
- There is no intermediate checkpoint and no second attempt — `predictions.csv`, your repository, your answers to the released question set, your AI error log, and your recommendation are all submitted together, once, at the end.
- Validate `predictions.csv` locally against this spec (row count, columns, types) before the deadline.

## 8. Reference forecast fallback

- Released at the midpoint of the event for teams who are behind.
- Using it does **not** replace or improve the forecast quality of your own final submission.
- If used, you must disclose this in your recommendation document.