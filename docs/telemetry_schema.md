# Telemetry Schema

This document describes the JSON telemetry packet format used by **Mission Support — Data Collector**.

All timestamps must be **UTC** and formatted using **ISO-8601**.

---

## Core Telemetry Fields

| Field        | Type   | Units    | Example                    | Required | Notes                                   |
|--------------|--------|----------|----------------------------|----------|-----------------------------------------|
| `mission_id` | string | —        | `"HASP-001"`               | **Yes**  | Identifies the mission / flight         |
| `timestamp`  | string | ISO-8601 | `"2026-01-03T21:14:52Z"`   | **Yes**  | Time reading was recorded (UTC)         |
| `lat`        | float  | degrees  | `18.2105`                  | **Yes**  | Range **−90 → 90**                      |
| `lon`        | float  | degrees  | `-66.0498`                 | **Yes**  | Range **−180 → 180**                    |
| `altitude_m` | float  | meters   | `14250.3`                  | **Yes**  | Altitude above sea level                |

> Required fields are enforced by the Pydantic model; ingest then applies extra validation rules and returns detailed error codes.

---

## Optional Motion / System Fields

| Field         | Type  | Units | Example | Required | Notes                                      |
|---------------|-------|-------|---------|----------|--------------------------------------------|
| `speed_mps`   | float | m/s   | `5.3`   | No       | Must be ≥ 0 if present; often backend-computed |
| `heading_deg` | float | deg   | `135.0` | No       | Must be in **[0, 360)**                    |
| `battery_pct` | float | %     | `82.0`  | No       | Must be in **[0, 100]**                    |

If not provided, the backend may compute `speed_mps` and `heading_deg` from recent telemetry history.

---

## Optional Environmental Fields

| Field           | Type  | Units | Example | Required | Notes                                                      |
|-----------------|-------|-------|---------|----------|------------------------------------------------------------|
| `temperature_c` | float | °C    | `-12.4` | No       | Rejected only if NaN                                      |
| `pressure_hpa`  | float | hPa   | `890.3` | No       | NaN is rejected; values outside **[300, 1100]** log a warning only |
| `humidity_pct`  | float | %     | `32.0`  | No       | Must be in **[0, 100]** if present                        |

---

## Validation Rules (Ingest)

A telemetry packet is rejected if **any** of the following are true:

### Required / core fields

- `mission_id` missing or empty string
- `lat`, `lon`, or `altitude_m` is **NaN**

### Bounds

- `lat` not in **[-90, 90]**
- `lon` not in **[-180, 180]**
- `altitude_m` outside **[-500, 50 000]**
- `battery_pct` present but not in **[0, 100]**
- `heading_deg` present but not in **[0, 360)**

### Time rules

- `timestamp` is more than **10 minutes older** than current UTC time

### Optional numeric fields

- `speed_mps` present but NaN or \< 0
- `temperature_c` present but NaN
- `pressure_hpa` present but NaN
- `humidity_pct` present but NaN or not in **[0, 100]**

Suspicious but not fatal:

- `pressure_hpa` outside **[300, 1100]** → logs a warning but is **not** rejected.

---

## Error Codes

`POST /telemetry` may return:

```json
{"status": "error", "reason": "missing_mission_id"}
{"status": "error", "reason": "nan_values"}
{"status": "error", "reason": "invalid_lat"}
{"status": "error", "reason": "invalid_lon"}
{"status": "error", "reason": "invalid_altitude"}
{"status": "error", "reason": "altitude_out_of_range"}
{"status": "error", "reason": "invalid_speed"}
{"status": "error", "reason": "invalid_heading"}
{"status": "error", "reason": "invalid_battery_pct"}
{"status": "error", "reason": "invalid_temperature"}
{"status": "error", "reason": "invalid_pressure"}
{"status": "error", "reason": "invalid_humidity"}
{"status": "error", "reason": "stale_timestamp"}

```
## On success:
```json
{"status": "saved", "total_points": <int>}
```
## Example Valid Payload

```json
{
  "mission_id": "HASP-001",
  "timestamp": "2026-01-03T21:14:52Z",
  "lat": 18.2105,
  "lon": -66.0498,
  "altitude_m": 14250.3,

  "temperature_c": -12.4,
  "pressure_hpa": 890.3,
  "humidity_pct": 32.0
}
```