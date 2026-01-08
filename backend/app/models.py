from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TelemetryPoint(BaseModel):
    mission_id: str
    lat: float
    lon: float
    altitude_m: float
    timestamp: datetime
    speed_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    battery_pct: Optional[float] = None
    temperature_c: Optional[float] = None
    pressure_hpa: Optional[float] = None
    humidity_pct: Optional[float] = None
