from fastapi import APIRouter, Query

from ..services.weather import fetch_daily_forecast, fetch_weather_data


router = APIRouter()


@router.get("/weather/current")
def current_weather(
    latitude: float = Query(54.3520, ge=-90, le=90),
    longitude: float = Query(18.6466, ge=-180, le=180),
):
    return fetch_weather_data(latitude, longitude)


@router.get("/weather/forecast")
def daily_weather_forecast(
    latitude: float = Query(54.3520, ge=-90, le=90),
    longitude: float = Query(18.6466, ge=-180, le=180),
):
    return fetch_daily_forecast(latitude, longitude)
