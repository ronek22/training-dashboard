from pydantic import BaseModel
from typing import Optional


METRIC_CATALOG = [
    {"key": "z2_pace", "label": "Z2 Pace", "unit": "s/km", "entry_mode": "manual", "description": "Aerobic pace benchmark. Store pace as seconds per kilometer."},
    {"key": "weight", "label": "Weight", "unit": "kg", "entry_mode": "manual", "description": "Body weight tracking."},
    {"key": "resting_hr", "label": "Resting HR", "unit": "bpm", "entry_mode": "manual", "description": "Morning or resting heart rate."},
    {"key": "ftp", "label": "FTP", "unit": "W", "entry_mode": "manual", "description": "Cycling functional threshold power."},
    {"key": "heel_pain", "label": "Heel Pain", "unit": "0-10", "entry_mode": "manual", "description": "Pain score on a 0-10 scale."},
    {"key": "streak", "label": "Streak", "unit": "days", "entry_mode": "computed", "description": "Computed automatically from consecutive activity days."},
]


class Metric(BaseModel):
    date: str
    metric: str
    value: float
    unit: Optional[str] = None
    notes: Optional[str] = None
