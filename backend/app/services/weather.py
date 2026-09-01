from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
UPCOMING_HOURS = 6


def _weather_description(code: int) -> str:
    if code == 0:
        return "Clear"
    if code in {1, 2}:
        return "Partly cloudy"
    if code == 3:
        return "Overcast"
    if code in {45, 48}:
        return "Foggy"
    if code in {51, 53, 55, 56, 57}:
        return "Drizzle"
    if code in {61, 63, 65, 66, 67}:
        return "Rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "Snow"
    if code in {80, 81, 82}:
        return "Rain showers"
    if code in {95, 96, 99}:
        return "Thunderstorm"
    return "Mixed conditions"


def summarize_weather_payload(payload: dict[str, Any], latitude: float, longitude: float) -> dict[str, Any]:
    current = payload.get("current") or {}
    hourly = payload.get("hourly") or {}
    current_time = str(current.get("time") or "")
    hourly_times = hourly.get("time") or []
    hourly_precipitation = hourly.get("precipitation") or []
    hourly_probability = hourly.get("precipitation_probability") or []

    upcoming = []
    for index, timestamp in enumerate(hourly_times):
        if current_time and str(timestamp) < current_time:
            continue
        precipitation = float(hourly_precipitation[index] or 0) if index < len(hourly_precipitation) else 0.0
        probability = int(hourly_probability[index] or 0) if index < len(hourly_probability) else 0
        upcoming.append(
            {
                "time": timestamp,
                "precipitation_mm": precipitation,
                "precipitation_probability": probability,
            }
        )
        if len(upcoming) == UPCOMING_HOURS:
            break

    total_precipitation = round(sum(hour["precipitation_mm"] for hour in upcoming), 1)
    peak_probability = max((hour["precipitation_probability"] for hour in upcoming), default=0)
    first_rain = next((hour for hour in upcoming if hour["precipitation_mm"] >= 0.1), None)
    weather_code = int(current.get("weather_code") or 0)

    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": payload.get("timezone"),
        "current": {
            "time": current_time,
            "temperature_c": round(float(current.get("temperature_2m") or 0)),
            "apparent_temperature_c": round(float(current.get("apparent_temperature") or 0)),
            "precipitation_mm": round(float(current.get("precipitation") or 0), 1),
            "weather_code": weather_code,
            "description": _weather_description(weather_code),
            "is_day": bool(current.get("is_day", 1)),
        },
        "upcoming": {
            "hours": len(upcoming),
            "rain_expected": total_precipitation >= 0.1,
            "precipitation_mm": total_precipitation,
            "peak_probability": peak_probability,
            "starts_at": first_rain["time"] if first_rain else None,
        },
    }


def fetch_weather_data(latitude: float, longitude: float) -> dict[str, Any]:
    try:
        response = httpx.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,precipitation,weather_code,is_day",
                "hourly": "precipitation,precipitation_probability",
                "forecast_days": 2,
                "timezone": "auto",
            },
            timeout=8,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Weather service is temporarily unavailable") from error

    return summarize_weather_payload(response.json(), latitude, longitude)
