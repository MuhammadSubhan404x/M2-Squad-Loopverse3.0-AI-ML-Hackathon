from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
expected = {(r["sensor_id"], r["target_date"]) for r in csv.DictReader((ROOT / "holdout" / "holdout_inputs.csv").open(encoding="utf-8"))}
with (ROOT / "predictions.csv").open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == 150, len(rows)
assert list(rows[0]) == ["sensor_id", "target_date", "predicted_pm25", "hazardous"]
actual = {(r["sensor_id"], r["target_date"]) for r in rows}
assert actual == expected and len(actual) == len(rows)
for row in rows:
    value = float(row["predicted_pm25"])
    assert math.isfinite(value) and value != -999
    assert row["hazardous"] in {"0", "1"}
print("PASS: 150 unique rows, exact columns, finite PM2.5 values, valid alarms")
