"""Leak-free baseline forecast and local advisory assistant."""

from __future__ import annotations

import csv
import math
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAZARDOUS_PM25 = 165.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _aqi_to_pm25(aqi: float) -> float:
    """Invert the EPA PM2.5 AQI breakpoints for the sensor's AQI readings."""
    breakpoints = (
        (0, 50, 0.0, 12.0),
        (51, 100, 12.1, 35.4),
        (101, 150, 35.5, 55.4),
        (151, 200, 55.5, 150.4),
        (201, 300, 150.5, 250.4),
        (301, 500, 250.5, 500.4),
    )
    value = min(max(aqi, 0.0), 500.0)
    for i_low, i_high, c_low, c_high in breakpoints:
        if value <= i_high:
            return c_low + (value - i_low) * (c_high - c_low) / (i_high - i_low)
    return 500.4


def load_history() -> dict[str, list[tuple[date, float]]]:
    metadata = {
        row["sensor_id"]: row for row in _read_csv(ROOT / "weather" / "sensor_metadata.csv")
    }
    history: dict[str, list[tuple[date, float]]] = {}
    for filename in ("batch_1_sensor_data.csv", "batch_2_sensor_data.csv"):
        batch_name = filename.removesuffix("_sensor_data.csv")
        for row in _read_csv(ROOT / "sensors" / filename):
            if float(row["reading_value"]) <= -998:
                continue
            sensor = row["sensor_id"]
            if metadata[sensor]["batch"] != batch_name:
                continue
            value = float(row["reading_value"])
            if metadata[sensor]["unit_type"] == "AQI":
                value = _aqi_to_pm25(value)
            # UTC observations are recorded at 19:00, which is midnight PKT.
            day = date.fromisoformat(row["timestamp"][:10])
            if metadata[sensor]["timezone"] == "UTC":
                day += timedelta(days=1)
            history.setdefault(sensor, []).append((day, value))
    for values in history.values():
        values.sort()
    return history


def _weather() -> dict[date, tuple[float, float, float]]:
    result = {}
    for row in _read_csv(ROOT / "weather" / "weather_history.csv"):
        result[date.fromisoformat(row["date"])] = (
            float(row["temp_c"]),
            float(row["humidity_pct"]),
            float(row["wind_kmh"]),
        )
    for row in _read_csv(ROOT / "holdout" / "holdout_weather.csv"):
        result[date.fromisoformat(row["date"])] = (
            float(row["temp_c"]),
            float(row["humidity_pct"]),
            float(row["wind_kmh"]),
        )
    return result


def _solve_ridge(rows: list[tuple[list[float], float]], width: int) -> list[float]:
    """Small dependency-free ridge regression solver using Gaussian elimination."""
    matrix = [[0.0] * (width + 1) for _ in range(width)]
    for features, target in rows:
        for i in range(width):
            matrix[i][width] += features[i] * target
            for j in range(width):
                matrix[i][j] += features[i] * features[j]
    for i in range(width):
        matrix[i][i] += 0.05 if i else 0.01
    for pivot in range(width):
        row = max(range(pivot, width), key=lambda r: abs(matrix[r][pivot]))
        matrix[pivot], matrix[row] = matrix[row], matrix[pivot]
        scale = matrix[pivot][pivot] or 1e-12
        for col in range(pivot, width + 1):
            matrix[pivot][col] /= scale
        for row in range(width):
            if row == pivot:
                continue
            scale = matrix[row][pivot]
            for col in range(pivot, width + 1):
                matrix[row][col] -= scale * matrix[pivot][col]
    return [matrix[i][width] for i in range(width)]


def _features(sensor: str, target: date, values: dict[date, float],
              weather: dict[date, tuple[float, float, float]],
              sensors: list[str]) -> list[float]:
    recent = [values[d] for d in sorted(values) if d < target]
    if len(recent) < 7 or target not in weather:
        raise ValueError("Insufficient history for forecast features")
    temp, humidity, wind = weather[target]
    sensor_effects = [1.0 if sensor == item else 0.0 for item in sensors]
    return [
        1.0,
        *sensor_effects,
        recent[-1],
        recent[-2],
        recent[-3],
        recent[-7],
        sum(recent[-3:]) / 3.0,
        sum(recent[-7:]) / 7.0,
        recent[-1] - recent[-7],
        temp,
        humidity,
        wind,
        math.sin(2.0 * math.pi * target.timetuple().tm_yday / 365.25),
        math.cos(2.0 * math.pi * target.timetuple().tm_yday / 365.25),
    ]


def _model_predictions() -> dict[tuple[str, date], float]:
    history = load_history()
    weather = _weather()
    sensors = sorted(history)
    values = {sensor: dict(entries) for sensor, entries in history.items()}
    training: list[tuple[list[float], float]] = []
    for sensor in sensors:
        dates = sorted(values[sensor])
        for target in dates[7:]:
            if target in weather:
                prior = {day: value for day, value in values[sensor].items() if day <= target}
                features = _features(sensor, target, prior, weather, sensors)
                training.append((features, values[sensor][target]))
    coefficients = _solve_ridge(training, len(training[0][0]))
    holdout = _read_csv(ROOT / "holdout" / "holdout_inputs.csv")
    targets = sorted({date.fromisoformat(row["target_date"]) for row in holdout})
    forecasts: dict[tuple[str, date], float] = {}
    for sensor in sensors:
        simulated = dict(values[sensor])
        for target in targets:
            features = _features(sensor, target, simulated, weather, sensors)
            prediction = sum(weight * value for weight, value in zip(coefficients, features))
            prediction = min(500.0, max(0.0, prediction))
            forecasts[(sensor, target)] = prediction
            simulated[target] = prediction
    return forecasts


def build_predictions() -> list[dict[str, str]]:
    metadata = {row["sensor_id"]: row for row in _read_csv(ROOT / "weather" / "sensor_metadata.csv")}
    forecasts = _model_predictions()
    holdout = _read_csv(ROOT / "holdout" / "holdout_inputs.csv")
    predictions = []
    for row in holdout:
        sensor = row["sensor_id"]
        target = date.fromisoformat(row["target_date"])
        if sensor not in metadata or (sensor, target) not in forecasts:
            raise RuntimeError("Holdout contains an unknown sensor/date pair")
        prediction = round(forecasts[(sensor, target)], 2)
        predictions.append(
            {
                "sensor_id": row["sensor_id"],
                "target_date": row["target_date"],
                "predicted_pm25": f"{prediction:.2f}",
                "hazardous": "1" if prediction >= HAZARDOUS_PM25 else "0",
            }
        )
    return predictions


def write_predictions() -> None:
    rows = build_predictions()
    output = ROOT / "predictions.csv.tmp"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sensor_id", "target_date", "predicted_pm25", "hazardous"],
        )
        writer.writeheader()
        writer.writerows(rows)
    output.replace(ROOT / "predictions.csv")


def _documents() -> list[tuple[str, str]]:
    documents = []
    for path in sorted((ROOT / "docs").glob("DOC-*.md")):
        documents.append((path.stem.split("_", 1)[0], path.read_text(encoding="utf-8")))
    return documents


def forecast(location: str, target_date: str) -> dict[str, object]:
    metadata = _read_csv(ROOT / "weather" / "sensor_metadata.csv")
    area_to_sensor = {row["area"].lower(): row["sensor_id"] for row in metadata}
    holdout = _read_csv(ROOT / "holdout" / "holdout_inputs.csv")
    valid_dates = {row["target_date"] for row in holdout}
    sensor = area_to_sensor.get(location.strip().lower())
    if sensor is None or target_date not in valid_dates:
        return {
            "location": location,
            "target_date": target_date,
            "pm25": None,
            "hazardous": None,
            "status": "unavailable",
            "source": "team_model",
        }
    for row in build_predictions():
        if row["sensor_id"] == sensor and row["target_date"] == target_date:
            value = float(row["predicted_pm25"])
            return {
                "location": location,
                "target_date": target_date,
                "pm25": value,
                "hazardous": value >= HAZARDOUS_PM25,
                "status": "ok",
                "source": "team_model",
            }
    raise RuntimeError("Holdout contract and predictions are inconsistent")


def ask(question: str) -> dict[str, object]:
    """Answer a question using keyword retrieval and the forecast tool."""
    question_id = "q-" + str(abs(hash(question)) % 10**8)
    lowered = question.lower()
    docs = _documents()
    terms = set(re.findall(r"[a-z0-9]+", lowered))
    ranked = sorted(
        (
            (len(terms & set(re.findall(r"[a-z0-9]+", text.lower()))), doc_id, text)
            for doc_id, text in docs
        ),
        reverse=True,
    )
    selected = [(doc_id, text) for score, doc_id, text in ranked[:3] if score > 0]
    location = next(
        (area for area in (row["area"] for row in _read_csv(ROOT / "weather" / "sensor_metadata.csv"))
         if area.lower() in lowered),
        None,
    )
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", question)
    forecast_intent = bool(re.search(r"\b(forecast|predict|prediction|pm2\.?5)\b", lowered))
    forecast_called = bool(forecast_intent and dates)
    sources = [doc_id for doc_id, _ in selected]
    if forecast_called:
        requested_location = location or "the requested location"
        result = forecast(requested_location, dates[0])
        if result["status"] == "unavailable":
            answer = f"I cannot provide a forecast for {requested_location} on {dates[0]} because it is outside the supported range."
            sources = []
        else:
            guidance = next((text for doc_id, text in docs if doc_id == "DOC-01"), "")
            sources = ["DOC-01"]
            level = "hazardous" if result["hazardous"] else "below the hazardous threshold"
            answer = (
                f"Our team forecast for {location} on {dates[0]} is {result['pm25']:.1f} "
                f"µg/m³, {level}. Follow the current health guidance: "
                f"{' '.join(guidance.split()[guidance.split().index('When') : guidance.split().index('When') + 18])}."
            )
    elif selected:
        # Retrieved text is evidence only; embedded instructions are never executed.
        answer = " ".join(
            " ".join(re.sub(r"SYSTEM NOTE.*", "", text, flags=re.I | re.S).strip().split()[:70])
            for _, text in selected
        )
    else:
        answer = "I can answer covered Lahore health, policy, and forecast questions when you provide a supported area and date."
    return {"question_id": question_id, "answer": answer, "sources": sources, "forecast_called": forecast_called}


if __name__ == "__main__":
    write_predictions()
    print("Wrote predictions.csv")
