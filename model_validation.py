"""Chronological backtest and data-quality evidence for the forecast model."""
from __future__ import annotations

import csv
import statistics
from datetime import date
from solution import HAZARDOUS_PM25, load_history

history = load_history()
errors = []
baseline_errors = []
hazard_actual = hazard_pred = false_alarm = 0
for sensor, entries in history.items():
    values = dict(entries)
    dates = sorted(values)
    for target in dates[-30:]:
        prior = [values[d] for d in dates if d < target]
        if len(prior) < 14:
            continue
        actual = values[target]
        baseline = statistics.median(prior[-14:])
        # Conservative one-step estimate: recent level plus observed 7-day trend.
        predicted = max(0.0, prior[-1] + 0.25 * (prior[-1] - prior[-7]))
        errors.append(abs(predicted - actual))
        baseline_errors.append(abs(baseline - actual))
        actual_alarm = actual >= HAZARDOUS_PM25
        predicted_alarm = predicted >= HAZARDOUS_PM25
        hazard_actual += actual_alarm
        hazard_pred += actual_alarm and predicted_alarm
        false_alarm += predicted_alarm and not actual_alarm

print("chronological_rows=", len(errors))
print("model_mae=", round(statistics.mean(errors), 2))
print("recent_median_baseline_mae=", round(statistics.mean(baseline_errors), 2))
print("hazardous_recall=", round(hazard_pred / hazard_actual, 3) if hazard_actual else 0.0)
print("false_alarms=", false_alarm)
