# app/db_models.py
from sqlalchemy import Column, Integer, Float, String, DateTime
from app.db import Base

class TelemetryPointORM(Base):
    __tablename__ = "telemetry_points"

    id = Column(Integer, primary_key=True, index=True)

    mission_id = Column(String, index=True, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    altitude_m = Column(Float, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    speed_mps = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    battery_pct = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
