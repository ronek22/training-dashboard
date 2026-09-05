from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class WeeklyReview(BaseModel):
    week_start: date
    improved: str = Field(min_length=1, max_length=1000)
    missed: str = Field(min_length=1, max_length=1000)
    proposed_change: str = Field(min_length=1, max_length=1000)
    previous_change_outcome: Literal['not_assessed', 'helped', 'did_not_help', 'not_tried'] = 'not_assessed'

    outcome_reason: str = Field(min_length=1, max_length=400)

    @field_validator('improved', 'missed', 'proposed_change', 'outcome_reason', mode='before')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('week_start')
    @classmethod
    def valid_week(cls, value):
        if value.weekday() != 0:
            raise ValueError('Week must start on Monday')
        due = datetime.combine(value + timedelta(days=6), time(23, 59), ZoneInfo('Europe/Warsaw'))
        if datetime.now(ZoneInfo('Europe/Warsaw')) < due:
            raise ValueError('Reviews are generated after Sunday at 23:59 Europe/Warsaw')
        return value
