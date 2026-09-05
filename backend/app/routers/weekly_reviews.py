from datetime import date

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models.weekly_reviews import WeeklyReview
from ..services.weekly_reviews import list_reviews, save_review, review_context

router = APIRouter()


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
