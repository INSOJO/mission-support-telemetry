from fastapi import APIRouter
from typing import Optional
import logging

from app.models import TelemetryPoint
from app.services.telemetry_service import ingest, latest, history
from app.storage.memory_store import get_recent_points
from app.services.trajectory_service import predict_path

from app.db import SessionLocal
from app.db_models import TelemetryPointORM

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/telemetry")
def ingest_telemetry(point: TelemetryPoint):
    logger.info(
        "POST /telemetry mission=%s lat=%s lon=%s alt=%s ts=%s",
        getattr(point, "mission_id", None),
        point.lat,
        point.lon,
        getattr(point, "altitude_m", None),
        point.timestamp,
    )
    return ingest(point)


@router.get("/telemetry/latest")
def get_latest(mission_id: Optional[str] = None):
    """
    Get the most recent telemetry point.
    If mission_id is provided, return the latest point for that mission only.
    """
    logger.info("GET /telemetry/latest mission_id=%s", mission_id)
    return latest(mission_id=mission_id)


@router.get("/telemetry")
def get_history(limit: int = 50, mission_id: Optional[str] = None):
    """
    Get recent telemetry points.
    If mission_id is provided, filter points to that mission.
    """
    logger.info("GET /telemetry history limit=%s mission_id=%s", limit, mission_id)
    return history(limit=limit, mission_id=mission_id)


@router.get("/trajectory/predict")
def trajectory_predict(
    seconds: int = 60,
    steps: int = 4,
    limit: int = 10,
    mission_id: Optional[str] = None,
):
    """
    Predict the trajectory based on recent points.
    If mission_id is provided, prediction uses only that mission's points.
    """
    logger.info(
        "GET /trajectory/predict seconds=%s steps=%s limit=%s mission_id=%s",
        seconds,
        steps,
        limit,
        mission_id,
    )
    points = get_recent_points(limit=limit, mission_id=mission_id)
    return predict_path(points=points, seconds=seconds, steps=steps)


@router.get("/missions")
def list_missions():
    """
    List distinct mission IDs present in the telemetry database.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(TelemetryPointORM.mission_id)
            .distinct()
            .order_by(TelemetryPointORM.mission_id)
            .all()
        )
        missions = [r[0] for r in rows]
        logger.info("GET /missions returned %s missions", len(missions))
        return {
            "status": "ok",
            "missions": missions,
            "count": len(missions),
        }
    finally:
        db.close()

@router.delete("/missions/{mission_id}")
def delete_mission(mission_id: str):
    """
    Delete all telemetry rows for a mission.
    """
    from app.db import SessionLocal
    from app.db_models import TelemetryPointORM

    db = SessionLocal()
    try:
        deleted = (
            db.query(TelemetryPointORM)
            .filter(TelemetryPointORM.mission_id == mission_id)
            .delete()
        )
        db.commit()
        logger.warning("Deleted %s rows for mission %s", deleted, mission_id)

        return {
            "status": "ok",
            "deleted": deleted,
            "mission_id": mission_id,
        }
    finally:
        db.close()
