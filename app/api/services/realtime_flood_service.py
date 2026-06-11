from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

import math
import pandas as pd
import numpy as np
import logging
import time
from app.config.database import get_db_session

from app.api.services.flood_model_service import run_flood_prediction
from app.internal.domain.iot_device import IotDevice
from app.internal.domain.iot_sensor_reading import IotSensorReading
from app.internal.domain.weather_data import WeatherData

from datetime import date, datetime, timedelta

from app.internal.domain.flood_prediction import FloodPrediction
from concurrent.futures import ThreadPoolExecutor,as_completed

logger = logging.getLogger(__name__)

def get_all_area_ids_with_weather(db: Session) -> list[str]:
    rows = (
        db.query(WeatherData.area_id)
        .distinct()
        .all()
    )

    return [str(row[0]) for row in rows if row[0] is not None]

def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)

def get_latest_device_by_area(db: Session, area_id: str) -> Optional[IotDevice]:
    return (
        db.query(IotDevice)
        .filter(IotDevice.area_id == area_id)
        .order_by(IotDevice.last_seen_at.desc().nullslast(), IotDevice.updated_at.desc())
        .first()
    )


def get_latest_sensor_reading(db: Session, device_id: str) -> Optional[IotSensorReading]:
    return (
        db.query(IotSensorReading)
        .filter(
            IotSensorReading.device_id == device_id,
            IotSensorReading.is_valid.is_(True),
        )
        .order_by(IotSensorReading.recorded_at.desc())
        .first()
    )


def get_latest_weather_by_area(db: Session, area_id: str) -> Optional[WeatherData]:
    return (
        db.query(WeatherData)
        .filter(WeatherData.area_id == area_id)
        .order_by(WeatherData.time.desc())
        .first()
    )


def predict_realtime_by_area(db: Session, area_id: str) -> Dict[str, Any]:
    weather_records = get_weather_history_by_area(db, area_id)

    if not weather_records:
        return {
            "status": "error",
            "message": "No weather data found for this area",
            "area_id": area_id,
        }

    if len(weather_records) < 192:
        return {
            "status": "error",
            "message": "Not enough weather history to build model features",
            "area_id": area_id,
            "records_found": len(weather_records),
            "records_required": 192,
        }

    weather_from = min(item.time for item in weather_records)
    weather_to = max(item.time for item in weather_records)

    latest_weather = max(weather_records, key=lambda item: item.time)

    features = build_features_from_weather_history(weather_records)

    payload = {
        "province": area_id,
        "area_id": area_id,
        "lat": None,
        "lon": None,
    }
    payload.update(features)

    prediction = run_flood_prediction(payload)
    
    saved_prediction = save_flood_prediction(
        db,
        latest_weather,
        prediction,
        weather_from,
        weather_to
    )

    prediction["status"] = "success"
    prediction["source"] = "ai_weather_model"
    prediction["area_id"] = area_id
    prediction["iot_available"] = False
    prediction["weather_time"] = latest_weather.time.isoformat() if latest_weather.time else None
    prediction["weather_records_used"] = len(weather_records)
    
    prediction["prediction_id"] = str(saved_prediction.id)
    prediction["predicted_at"] = saved_prediction.predicted_at.isoformat()

    return prediction

def _wind_to_uv(wind_speed: float, wind_direction: float) -> tuple[float, float]:
    wd_rad = math.radians(wind_direction or 0.0)
    u10 = -wind_speed * math.sin(wd_rad)
    v10 = -wind_speed * math.cos(wd_rad)
    return u10, v10


def get_weather_history_by_area(
    db: Session,
    area_id: str,
) -> list[WeatherData]:

    return (
        db.query(WeatherData)
        .filter(WeatherData.area_id == area_id)
        .order_by(WeatherData.time.desc())
        .limit(192)
        .all()
    )


def build_features_from_weather_history(records: list[WeatherData]) -> Dict[str, Any]:

    if len(records) < 192:
        raise ValueError("Need at least 192 hourly weather records")

    rows = []

    for item in records:
        rainfall = _to_float(item.rainfall) or 0.0
        temperature = _to_float(item.temperature) or 0.0
        dewpoint = _to_float(item.dewpoint) or 0.0
        pressure = _to_float(item.pressure) or 0.0
        wind_speed = _to_float(item.wind_speed) or 0.0
        wind_direction = _to_float(item.wind_direction) or 0.0
        humidity = _to_float(item.humidity) or 0.0
        evapotranspiration = _to_float(item.evapotranspiration) or 0.0

        u10, v10 = _wind_to_uv(wind_speed, wind_direction)

        rows.append({
            "time": item.time,
            "precip": rainfall,
            "temp": temperature,
            "dewpoint": dewpoint,
            "pressure": pressure,
            "windspeed": wind_speed,
            "humidity": humidity,
            "evap": evapotranspiration,
            "u10": u10,
            "v10": v10,
        })

    hourly_df = pd.DataFrame(rows)

    hourly_df["date"] = pd.to_datetime(hourly_df["time"]).dt.date

    daily_df = hourly_df.groupby("date").agg(
        tp_mean=("precip", "mean"),
        tp_max=("precip", "max"),
        tp_p90=("precip", lambda x: np.percentile(x, 90)),
        tp_p99=("precip", lambda x: np.percentile(x, 99)),
        t2m_mean=("temp", "mean"),
        t2m_max=("temp", "max"),
        d2m_mean=("dewpoint", "mean"),
        rh_mean=("humidity", "mean"),
        sp_mean=("pressure", "mean"),
        ws_mean=("windspeed", "mean"),
        ws_max=("windspeed", "max"),
        evap_mean=("evap", "sum"),
        u10_mean=("u10", "mean"),
        v10_mean=("v10", "mean"),
    ).reset_index()

    daily_df["ro_mean"] = daily_df["tp_mean"] * 0.15
    daily_df["ro_max"] = daily_df["tp_max"] * 0.20

    daily_df["date"] = daily_df["date"].astype(str)

    df = daily_df.sort_values("date").reset_index(drop=True)

    if len(df) < 8:
        raise ValueError("Need at least 8 daily records")

    today = df.iloc[-1]
    hist = df.iloc[:-1]

    features = {}

    for col in [
        "tp_mean", "tp_max", "tp_p90", "tp_p99",
        "t2m_mean", "t2m_max", "d2m_mean", "rh_mean",
        "sp_mean", "ws_mean", "ws_max", "evap_mean",
        "ro_mean", "ro_max", "u10_mean", "v10_mean",
    ]:
        features[col] = float(today.get(col, 0.0))

    dt = pd.to_datetime(today["date"])
    features["month"] = float(dt.month)
    features["doy"] = float(dt.dayofyear)

    lag_vars = [
        "tp_mean", "tp_max", "tp_p90",
        "ro_max", "ro_mean",
        "ws_max", "rh_mean",
        "sp_mean", "u10_mean", "v10_mean"
    ]

    for lag in range(1, 8):
        idx = len(hist) - lag

        for var in lag_vars:
            features[f"{var}_lag{lag}"] = (
                float(hist.iloc[idx][var])
                if idx >= 0
                else 0.0
            )

    for w, suffix in [(3, "3d"), (5, "5d"), (7, "7d")]:
        window = df.tail(w + 1).head(w)

        features[f"tp_max_{suffix}"] = float(window["tp_max"].max())
        features[f"tp_mean_{suffix}"] = float(window["tp_mean"].mean())

        if suffix in ("3d", "7d"):
            features[f"ro_max_{suffix}"] = float(window["ro_max"].max())

    api = 0.0

    for _, row in df.iterrows():
        api = 0.85 * api + row["tp_mean"]

    features["api"] = float(api)

    return features

def save_flood_prediction(
    db: Session,
    weather: WeatherData,
    prediction: Dict[str, Any],
    weather_from,
    weather_to,
    sensor_reading_id: Optional[str] = None,
) -> FloodPrediction:
    
    today=date.today() #Ngày AI chạy

    record = FloodPrediction(
        sensor_reading_id=sensor_reading_id,

        lead1_probability=prediction["forecast"]["day_1"]["probability"],
        lead2_probability=prediction["forecast"]["day_2"]["probability"],
        lead3_probability=prediction["forecast"]["day_3"]["probability"],

        lead1=prediction["forecast"]["day_1"]["risk_level"],
        lead2=prediction["forecast"]["day_2"]["risk_level"],
        lead3=prediction["forecast"]["day_3"]["risk_level"],
        
        lead1_date=today,
        lead2_date=today + timedelta(days=1),
        lead3_date=today + timedelta(days=2),

        predicted_at=datetime.now(),
        weather_from=weather_from,
        weather_to=weather_to,
        area_id=weather.area_id,
    )

    db.add(record)
    db.flush()

    return record

def predict_all_areas() -> Dict[str, Any]:
    logger.info("START BACKGROUND PREDICTION")
    start = time.perf_counter()

    db = get_db_session()
    try:
        area_ids = get_all_area_ids_with_weather(db)
    finally:
        db.close()

    processed = errors = high_risk = 0
    total = len(area_ids)
    logger.info("Total areas found=%s", total)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_predict_one_area, area_id): area_id
            for area_id in area_ids
        }

        for i, future in enumerate(as_completed(futures), 1):
            area_id = futures[future]
            try:
                result = future.result()
                if result.get("status") == "success":
                    processed += 1
                    if any(
                        d.get("risk_level") == "HIGH"
                        for d in result.get("forecast", {}).values()
                    ):
                        high_risk += 1
                else:
                    errors += 1
                    logger.warning(
                        "Prediction skipped area=%s reason=%s",
                        area_id,
                        result.get("message"),
                    )
            except Exception:
                errors += 1
                logger.exception("Prediction failed area=%s", area_id)

            if i % 100 == 0:
                logger.info(
                    "Progress %s/%s processed=%s errors=%s",
                    i, total, processed, errors,
                )

    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "Finished: total=%s processed=%s high_risk=%s errors=%s duration_ms=%s",
        total, processed, high_risk, errors, duration_ms,
    )

    return {
        "status": "success",
        "total": total,
        "processed": processed,
        "high_risk": high_risk,
        "errors": errors,
        "duration_ms": duration_ms,
    }

def _predict_one_area(area_id: str)-> Dict[str, Any]:
    # Mỗi thread dùng session riêng
    db=get_db_session()
    try:
        return predict_realtime_by_area(db,area_id)
    finally:
        db.close()