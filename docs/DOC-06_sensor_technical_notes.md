---
document_id: DOC-06
title: Sensor Network Technical Notes
authority: Lahore Smog Intelligence Challenge — Organizers
published_date: 2026-10-20
status: current
---

# Sensor Network Technical Notes

The challenge covers two independently operated sensor networks across 15 Lahore areas.

**Network A**
- Reports raw PM2.5 concentration (µg/m³).
- Timestamps recorded in UTC.
- Known issue: occasional sentinel value `-999` indicates sensor malfunction or communication failure — treat as missing, not as a real reading of -999.

**Network B**
- Reports AQI (Air Quality Index), not raw PM2.5.
- Timestamps recorded in Pakistan Standard Time (UTC+5).
- Same `-999` missing-value convention applies.

**Known data quality issue**
One sensor in the historical data (undisclosed ID) experienced a stuck/flat-line reading for three consecutive days due to a hardware fault. Teams are expected to detect and handle this during data auditing — see Trap #3 in the Participant Handbook.

**Coverage**
The network covers 15 named areas of Lahore. Locations outside this list (including other cities) are not covered and have no forecast available.
