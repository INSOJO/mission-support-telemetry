from typing import Optional
import math
import logging
from datetime import datetime, timezone, timedelta

from app.models import TelemetryPoint
from app.storage.memory_store import (
    add_point,
    get_latest_point,
    get_points,
    count_points,
)

logger = logging.getLogger(__name__)


def _is_nan(value: Optional[float]) -> bool:
    return value is not None and math.isnan(value)


def ingest(point: TelemetryPoint) -> dict:
    """
    Validate and ingest a telemetry point into the store.
    Returns a small status dict that the API can send back.
    """

    # Required: mission_id
    if not point.mission_id or not point.mission_id.strip():
        logger.warning("Rejected packet: missing mission_id")
        return {"status": "error", "reason": "missing_mission_id"}

    # Required: lat / lon basic validity
    if _is_nan(point.lat) or _is_nan(point.lon):
        logger.warning("Rejected packet: invalid coordinates (NaN)")
        return {"status": "error", "reason": "nan_values"}

    if not (-90.0 <= point.lat <= 90.0):
        logger.warning("Rejected packet: latitude out of range %s", point.lat)
        return {"status": "error", "reason": "invalid_lat"}

    if not (-180.0 <= point.lon <= 180.0):
        logger.warning("Rejected packet: longitude out of range %s", point.lon)
        return {"status": "error", "reason": "invalid_lon"}

    # Required: altitude
    if _is_nan(point.altitude_m):
        logger.warning("Rejected packet: invalid altitude (NaN)")
        return {"status": "error", "reason": "invalid_altitude"}

    # Optional sanity check: homever it can be changed to meet mission criteria
    if not (-500.0 <= point.altitude_m <= 50000.0):
        logger.warning("Rejected packet: altitude out of range %s", point.altitude_m)
        return {"status": "error", "reason": "altitude_out_of_range"}

    # Required: timestamp freshness
    now = datetime.now(timezone.utc)
    if point.timestamp < now - timedelta(minutes=10):
        logger.warning("Rejected packet: stale timestamp %s", point.timestamp)
        return {"status": "error", "reason": "stale_timestamp"}

    # Optional: speed_mps 
    if point.speed_mps is not None:
        if _is_nan(point.speed_mps) or point.speed_mps < 0.0:
            logger.warning("Rejected packet: invalid speed_mps %s", point.speed_mps)
            return {"status": "error", "reason": "invalid_speed"}

    # Optional: heading_deg
    if point.heading_deg is not None:
        if _is_nan(point.heading_deg) or not (0.0 <= point.heading_deg < 360.0):
            logger.warning("Rejected packet: invalid heading_deg %s", point.heading_deg)
            return {"status": "error", "reason": "invalid_heading"}

    # Optional: battery_pct
    if point.battery_pct is not None:
        if _is_nan(point.battery_pct) or not (0.0 <= point.battery_pct <= 100.0):
            logger.warning(
                "Rejected packet: invalid battery_pct %s", point.battery_pct
            )
            return {"status": "error", "reason": "invalid_battery_pct"}

    # Optional: temperature_c
    if point.temperature_c is not None and _is_nan(point.temperature_c):
        logger.warning("Rejected packet: invalid temperature_c (NaN)")
        return {"status": "error", "reason": "invalid_temperature"}

    # Optional: pressure_hpa
    if point.pressure_hpa is not None:
        if _is_nan(point.pressure_hpa):
            logger.warning("Rejected packet: invalid pressure_hpa (NaN)")
            return {"status": "error", "reason": "invalid_pressure"}
        # Caution: This sanity check only warns the user doesnt reject the packet can
        # be change to fit mission criteria
        if not (300.0 <= point.pressure_hpa <= 1100.0):
            logger.warning("Suspicious pressure_hpa value %s", point.pressure_hpa)

    if point.humidity_pct is not None:
        if _is_nan(point.humidity_pct) or not (0.0 <= point.humidity_pct <= 100.0):
            logger.warning(
                "Rejected packet: invalid humidity_pct %s", point.humidity_pct
            )
            return {"status": "error", "reason": "invalid_humidity"}

    add_point(point)
    logger.info(
        "Saving telemetry point mission=%s lat=%s lon=%s alt=%s ts=%s",
        point.mission_id,
        point.lat,
        point.lon,
        point.altitude_m,
        point.timestamp,
    )

    return {
        "status": "saved",
        "total_points": count_points(mission_id=point.mission_id),
    }


def latest(mission_id: str | None = None) -> dict:
    """
    Return the latest telemetry point (if any).
    If mission_id is provided, restrict to that mission.
    """
    point = get_latest_point(mission_id=mission_id)
    if point is None:
        logger.info("Empty: no available latest point (mission_id=%s)", mission_id)
        return {"status": "empty", "latest": None}

    logger.info("Showing latest telemetry point (mission_id=%s)", mission_id)
    return {"status": "ok", "latest": point.model_dump()}


def history(limit: int = 50, mission_id: str | None = None) -> dict:
    """
    Return up to `limit` most recent telemetry points.
    If mission_id is provided, restrict to that mission.
    """
    points = get_points(limit=limit, mission_id=mission_id)
    logger.info(
        "Returning %d telemetry points (limit=%s, mission_id=%s)",
        len(points),
        limit,
        mission_id,
    )
    return {
        "status": "ok",
        "count": len(points),
        "points": [p.model_dump() for p in points],
    }
