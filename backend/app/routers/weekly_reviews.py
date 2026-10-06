from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models.weekly_reviews import WeeklyReview
from ..services.week_wins import build_week_wins
from ..services.weekly_reviews import list_reviews, monthly_goal_review, save_review, review_context, review_status

router = APIRouter()


@router.get('/reviews/weekly/status')
def get_weekly_review_status():
    conn = get_db()
    try:
        return review_status(conn)
    finally:
        conn.close()


@router.get('/reviews/weekly')
def get_weekly_reviews():
    conn = get_db()
    try:
        return list_reviews(conn)
    finally:
        conn.close()


@router.put('/reviews/weekly')
def put_weekly_review(review: WeeklyReview):
    conn = get_db()
    try:
        return save_review(conn, review)
    finally:
        conn.close()


@router.get('/reviews/weekly/context')
def get_weekly_review_context(week_start: date):
    if week_start.weekday() != 0:
        raise HTTPException(422, 'Week must start on Monday')
    conn = get_db()
    try:
        return review_context(conn, week_start)
    finally:
        conn.close()


@router.get('/reviews/weekly/goals')
def get_weekly_review_goals(week_start: date):
    if week_start.weekday() != 0:
        raise HTTPException(422, 'Week must start on Monday')
    conn = get_db()
    try:
        return {'goals': monthly_goal_review(conn, week_start)}
    finally:
        conn.close()


@router.get('/reviews/weekly/wins')
def get_week_wins(week_start: Optional[date] = None, day: Optional[date] = None):
    """Three wins and one focus; ``day`` is the browser's local date (the container clock is UTC)."""
    conn = get_db()
    try:
        return build_week_wins(conn, week_start, today=day)
    finally:
        conn.close()
