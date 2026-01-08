# app/storage/memory_store.py

from typing import List, Optional
import logging

from sqlalchemy import func

from app.db import SessionLocal
from app.db_models import TelemetryPointORM
from app.models import TelemetryPoint

logger = logging.getLogger(__name__)


def _row_to_model(row: TelemetryPointORM) -> TelemetryPoint:
    """Convert a SQLAlchemy row to the Pydantic TelemetryPoint."""
    return TelemetryPoint(
        mission_id=row.mission_id,
        lat=row.lat,
        lon=row.lon,
        altitude_m=row.altitude_m,
        timestamp=row.timestamp,
        speed_mps=row.speed_mps,
        heading_deg=row.heading_deg,
        battery_pct=row.battery_pct,
        temperature_c=row.temperature_c,
        pressure_hpa=row.pressure_hpa,
        humidity_pct=row.humidity_pct,
    )


def add_point(point: TelemetryPoint) -> None:
    """Persist a telemetry point into the DB."""
    db = SessionLocal()
    try:
        row = TelemetryPointORM(
            mission_id=point.mission_id,
            lat=point.lat,
            lon=point.lon,
            altitude_m=point.altitude_m,
            timestamp=point.timestamp,
            speed_mps=getattr(point, "speed_mps", None),
            heading_deg=getattr(point, "heading_deg", None),
            battery_pct=getattr(point, "battery_pct", None),
            temperature_c=getattr(point, "temperature_c", None),
            pressure_hpa=getattr(point, "pressure_hpa", None),
            humidity_pct=getattr(point, "humidity_pct", None),
        )
        db.add(row)
        db.commit()
        logger.debug(
            "DB add_point: mission=%s lat=%s lon=%s ts=%s",
            row.mission_id, row.lat, row.lon, row.timestamp
        )
    finally:
        db.close()


def get_latest_point(mission_id: Optional[str] = None) -> Optional[TelemetryPoint]:
    """
    Return the most recent telemetry point by timestamp.
    If mission_id is provided, filter only that mission.
    """
    db = SessionLocal()
    try:
        query = db.query(TelemetryPointORM)
        if mission_id:
            query = query.filter(TelemetryPointORM.mission_id == mission_id)

        row = query.order_by(TelemetryPointORM.timestamp.desc()).first()
        if row is None:
            logger.debug(
                "get_latest_point: DB empty (mission_id=%s)",
                mission_id,
            )
            return None

        logger.debug(
            "get_latest_point: returning timestamp %s (mission_id=%s)",
            row.timestamp,
            mission_id,
        )
        return _row_to_model(row)
    finally:
        db.close()


def get_points(limit: int = 50, mission_id: Optional[str] = None) -> List[TelemetryPoint]:
    """
    Return up to `limit` most recent points (newest first).
    If mission_id is provided, filter only that mission.
    """
    db = SessionLocal()
    try:
        query = db.query(TelemetryPointORM)
        if mission_id:
            query = query.filter(TelemetryPointORM.mission_id == mission_id)

        rows = (
            query
            .order_by(TelemetryPointORM.timestamp.desc())
            .limit(limit)
            .all()
        )
        logger.debug(
            "get_points: limit=%s, returned=%s from DB (mission_id=%s)",
            limit, len(rows), mission_id
        )
        return [_row_to_model(r) for r in rows]
    finally:
        db.close()


def get_recent_points(limit: int = 10, mission_id: Optional[str] = None) -> List[TelemetryPoint]:
    """
    Return up to `limit` most recent points, sorted oldest -> newest.
    Used by trajectory prediction.
    If mission_id is provided, filter only that mission.
    """
    if limit <= 0:
        logger.debug("get_recent_points called with non-positive limit=%s", limit)
        return []

    db = SessionLocal()
    try:
        query = db.query(TelemetryPointORM)
        if mission_id:
            query = query.filter(TelemetryPointORM.mission_id == mission_id)

        rows = (
            query
            .order_by(TelemetryPointORM.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows = list(reversed(rows)) 
        logger.debug(
            "get_recent_points: limit=%s, returned=%s from DB (mission_id=%s)",
            limit, len(rows), mission_id
        )
        return [_row_to_model(r) for r in rows]
    finally:
        db.close()


def count_points(mission_id: Optional[str] = None) -> int:
    """
    Count points, optionally restricted to one mission.
    """
    db = SessionLocal()
    try:
        query = db.query(func.count(TelemetryPointORM.id))
        if mission_id:
            query = query.filter(TelemetryPointORM.mission_id == mission_id)

        total = query.scalar() or 0
        logger.debug("count_points: total=%s (mission_id=%s)", total, mission_id)
        return total
    finally:
        db.close()
