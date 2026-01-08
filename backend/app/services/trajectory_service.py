from __future__ import annotations

from datetime import timedelta
from math import cos, radians, atan2, sqrt, pi
from typing import Dict, List

from app.models import TelemetryPoint

import logging

logger = logging.getLogger(__name__)


"""
Trajectory prediction service (EXPERIMENTAL).

This implementation provides a short-term trajectory estimate based on recent
telemetry using simple velocity projection and uncertainty growth.

Due to the chaotic nature of high-altitude balloon dynamics (wind shear,
vertical coupling, turbulence), this approach is only reliable over short
time horizons (seconds to a few minutes).

Long-term prediction accuracy is limited and intentionally conservative.

Future work:
- Replace or augment this model with a machine-learning-based predictor
  trained on historical mission data.
- Integrate atmospheric wind models for altitude-dependent drift correction.

This module is designed to be swappable without changes to API consumers.
"""



EARTH_RADIUS_M = 6371000.0


def _to_meters_delta(lat0: float, lon0: float, lat1: float, lon1: float) -> tuple[float, float]:
    """
    Convert small lat/lon changes into meters using an equirectangular approximation.
    Returns (north_m, east_m).
    Good enough for short time steps and nearby points.
    """
    dlat = radians(lat1 - lat0)
    dlon = radians(lon1 - lon0)
    lat_avg = radians((lat0 + lat1) / 2.0)

    north_m = dlat * EARTH_RADIUS_M
    east_m = dlon * EARTH_RADIUS_M * cos(lat_avg)
    return north_m, east_m


def _from_meters_delta(lat0: float, lon0: float, north_m: float, east_m: float) -> tuple[float, float]:
    """
    Convert meters back to lat/lon deltas.
    """
    lat_avg = radians(lat0)
    dlat = (north_m / EARTH_RADIUS_M) * (180.0 / pi)
    denom = (EARTH_RADIUS_M * cos(lat_avg))
    if abs(denom) < 1e-9:
        dlon = 0.0
    else:
        dlon = (east_m / denom) * (180.0 / pi)

    return lat0 + dlat, lon0 + dlon


def _estimate_velocity(points: List[TelemetryPoint]) -> Dict[str, float]:
    """
    Estimate velocity using the last two points.
    Returns velocities in meters/sec: vn (north), ve (east), vz (alt),
    plus total horizontal speed and heading_deg.
    """
    p0 = points[-2]
    p1 = points[-1]

    dt = (p1.timestamp - p0.timestamp).total_seconds()
    if dt <= 0:
        logger.warning(
            "Velocity estimation: non-positive dt=%s between %s and %s, treating as stationary",
            dt, p0.timestamp, p1.timestamp
        )
        try:
            p1.speed_mps = 0.0
            p1.heading_deg = 0.0
        except Exception:
            pass
        return {"vn": 0.0, "ve": 0.0, "vz": 0.0, "speed": 0.0, "heading_deg": 0.0}

    north_m, east_m = _to_meters_delta(p0.lat, p0.lon, p1.lat, p1.lon)
    vn = north_m / dt
    ve = east_m / dt
    vz = (p1.altitude_m - p0.altitude_m) / dt

    speed = sqrt(vn * vn + ve * ve)

    if speed > 0:
        heading_rad = atan2(ve, vn) 
        heading_deg = (heading_rad * 180.0 / pi) % 360.0
    else:
        heading_deg = 0.0

    try:
        p1.speed_mps = speed
        p1.heading_deg = heading_deg
    except Exception:
        pass

    logger.info(
        "Estimated velocity vn=%.2f m/s ve=%.2f m/s vz=%.2f m/s, "
        "speed=%.2f m/s heading=%.1f° over dt=%.2fs",
        vn, ve, vz, speed, heading_deg, dt
    )

    return {"vn": vn, "ve": ve, "vz": vz, "speed": speed, "heading_deg": heading_deg}


def _uncertainty_radius(seconds_ahead: float, speed_mps: float) -> float:
    """
    Simple uncertainty model:
    - base sensor noise
    - grows with time (drift)
    - increases a bit with speed
    """
    base = 60.0                        
    drift = 4.0 * seconds_ahead        
    speed_term = 0.5 * speed_mps * seconds_ahead  
    return base + drift + speed_term


def predict_path(
    points: List[TelemetryPoint],
    seconds: int = 60,
    steps: int = 4
) -> Dict:
    """
    Build a future path suitable for a map.
    - seconds: total time horizon ahead
    - steps: number of future points (e.g., 4 means t=15,30,45,60 if seconds=60)
    """
    if len(points) < 2:
        logger.warning(
            "predict_path called with not enough points: %s (need at least 2)",
            len(points)
        )
        return {"status": "not_enough_data", "reason": "need_at_least_2_points"}

    if seconds <= 0:
        logger.warning("predict_path received non-positive seconds=%s, defaulting to 60", seconds)
        seconds = 60
    if steps <= 0:
        logger.warning("predict_path received non-positive steps=%s, defaulting to 4", steps)
        steps = 4

    current = points[-1]
    logger.info(
        "Starting prediction from lat=%.6f lon=%.6f alt=%.1f with %s points, horizon=%ss, steps=%s",
        current.lat, current.lon, current.altitude_m, len(points), seconds, steps
    )

    v = _estimate_velocity(points)
    vn, ve, vz = v["vn"], v["ve"], v["vz"]
    speed = v["speed"]
    heading_deg = v["heading_deg"]

    dt_step = seconds / steps
    path = []

    for i in range(1, steps + 1):
        t = dt_step * i

        north = vn * t
        east = ve * t
        alt = current.altitude_m + (vz * t)

        lat_pred, lon_pred = _from_meters_delta(current.lat, current.lon, north, east)
        ts_pred = current.timestamp + timedelta(seconds=t)

        radius = _uncertainty_radius(t, speed)

        path.append({
            "t": int(round(t)),
            "lat": lat_pred,
            "lon": lon_pred,
            "altitude_m": alt,
            "timestamp": ts_pred.isoformat(),
            "uncertainty_m": radius,
            "speed_mps": speed,
            "heading_deg": heading_deg,
            "mission_id": current.mission_id,  
        })

    final = path[-1]
    logger.info(
        "Prediction complete: horizon=%ss, steps=%s, final lat=%.6f lon=%.6f alt=%.1f speed=%.2f m/s heading=%.1f°",
        seconds, steps,
        final["lat"], final["lon"], final["altitude_m"],
        speed, heading_deg
    )

    return {
        "status": "ok",
        "seconds": seconds,
        "steps": steps,
        "based_on_points": len(points),
        "current": current.model_dump(),
        "velocity_mps": {
            "north": vn,
            "east": ve,
            "vertical": vz,
            "speed": speed,
            "heading_deg": heading_deg,
        },
        "prediction": path[-1],
        "path": path
    }
