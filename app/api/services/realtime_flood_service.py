from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

import math
import pandas as pd
import logging
import time
from app.config.database import get_db_session

from app.api.services.flood_model_service import run_flood_prediction
from app.internal.domain.iot_device import IotDevice
from app.internal.domain.iot_sensor_reading import IotSensorReading
from app.internal.domain.weather_data import WeatherData

from datetime import datetime

from app.internal.domain.flood_prediction import FloodPrediction

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


def _weather_to_payload(weather: WeatherData, device: Optional[IotDevice] = None) -> Dict[str, Any]:
    lat = _to_float(device.lat) if device else None
    lon = _to_float(device.lon) if device else None

    return {
        "province": weather.area_id,
        "area_id": weather.area_id,
        "lat": lat,
        "lon": lon,
        "rainfall": _to_float(weather.rainfall),
        "temperature": _to_float(weather.temperature),
        "dewpoint": _to_float(weather.dewpoint),
        "pressure": _to_float(weather.pressure),
        "wind_speed": _to_float(weather.wind_speed),
        "wind_direction": _to_float(weather.wind_direction),
        "humidity": _to_float(weather.humidity),
        "evapotranspiration": _to_float(weather.evapotranspiration),
    }


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
    weather_records = get_weather_history_by_area(db, area_id, limit=8)

    if not weather_records:
        return {
            "status": "error",
            "message": "No weather data found for this area",
            "area_id": area_id,
        }

    if len(weather_records) < 8:
        return {
            "status": "error",
            "message": "Not enough weather history to build model features",
            "area_id": area_id,
            "records_found": len(weather_records),
            "records_required": 8,
        }

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
    
    saved_prediction = save_flood_prediction(db, latest_weather, prediction)

    prediction["status"] = "success"
    prediction["source"] = "ai_weather_model"
    prediction["area_id"] = area_id
    prediction["iot_available"] = False
    prediction["weather_time"] = latest_weather.time.isoformat() if latest_weather.time else None
    prediction["weather_records_used"] = len(weather_records)
    
    prediction["prediction_id"] = str(saved_prediction.id)
    prediction["weather_data_id"] = str(saved_prediction.madulieu)
    prediction["predicted_at"] = saved_prediction.predicted_at.isoformat()

    return prediction

def _wind_to_uv(wind_speed: float, wind_direction: float) -> tuple[float, float]:
    wd_rad = math.radians(wind_direction or 0.0)
    u10 = -wind_speed * math.sin(wd_rad)
    v10 = -wind_speed * math.cos(wd_rad)
    return u10, v10


def get_weather_history_by_area(db: Session, area_id: str, limit: int = 8) -> list[WeatherData]:
    return (
        db.query(WeatherData)
        .filter(WeatherData.area_id == area_id)
        .order_by(WeatherData.time.desc())
        .limit(limit)
        .all()
    )


def build_features_from_weather_history(records: list[WeatherData]) -> Dict[str, Any]:
    if len(records) < 2:
        raise ValueError("Need at least 2 weather records to build prediction features")

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
            "date": item.time.date().isoformat(),
            "tp_mean": rainfall,
            "tp_max": rainfall,
            "tp_p90": rainfall,
            "tp_p99": rainfall,
            "t2m_mean": temperature,
            "t2m_max": temperature,
            "d2m_mean": dewpoint,
            "rh_mean": humidity,
            "sp_mean": pressure,
            "ws_mean": wind_speed,
            "ws_max": wind_speed,
            "evap_mean": evapotranspiration,
            "u10_mean": u10,
            "v10_mean": v10,
            "ro_mean": rainfall * 0.15,
            "ro_max": rainfall * 0.20,
        })

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    today = df.iloc[-1]
    hist = df.iloc[:-1]

    features = {}

    current_cols = [
        "tp_mean", "tp_max", "tp_p90", "tp_p99",
        "t2m_mean", "t2m_max", "d2m_mean", "rh_mean",
        "sp_mean", "ws_mean", "ws_max", "evap_mean",
        "ro_mean", "ro_max", "u10_mean", "v10_mean",
    ]

    for col in current_cols:
        features[col] = float(today.get(col, 0.0))

    dt = pd.to_datetime(today["date"])
    features["month"] = float(dt.month)
    features["doy"] = float(dt.dayofyear)

    lag_vars = [
        "tp_mean", "tp_max", "tp_p90", "ro_max", "ro_mean",
        "ws_max", "rh_mean", "sp_mean", "u10_mean", "v10_mean",
    ]

    for lag in range(1, 8):
        idx = len(hist) - lag
        for var in lag_vars:
            features[f"{var}_lag{lag}"] = float(hist.iloc[idx][var]) if idx >= 0 else 0.0

    for w, suffix in [(3, "3d"), (5, "5d"), (7, "7d")]:
        window = df.tail(w + 1).head(w)
        features[f"tp_max_{suffix}"] = float(window["tp_max"].max()) if not window.empty else 0.0
        features[f"tp_mean_{suffix}"] = float(window["tp_mean"].mean()) if not window.empty else 0.0

        if suffix in ("3d", "7d"):
            features[f"ro_max_{suffix}"] = float(window["ro_max"].max()) if not window.empty else 0.0

    api = 0.0
    for _, row in df.iterrows():
        api = 0.85 * api + row["tp_mean"]

    features["api"] = float(api)

    return features

def save_flood_prediction(
    db: Session,
    weather: WeatherData,
    prediction: Dict[str, Any],
    sensor_reading_id: Optional[str] = None,
) -> FloodPrediction:

    record = FloodPrediction(
        madulieu=weather.id,
        sensor_reading_id=sensor_reading_id,

        lead1_probability=prediction["forecast"]["day_1"]["probability"],
        lead2_probability=prediction["forecast"]["day_2"]["probability"],
        lead3_probability=prediction["forecast"]["day_3"]["probability"],

        lead1=prediction["forecast"]["day_1"]["risk_level"],
        lead2=prediction["forecast"]["day_2"]["risk_level"],
        lead3=prediction["forecast"]["day_3"]["risk_level"],

        predicted_at=datetime.now(),
        area_id=weather.area_id,
    )

    db.add(record)
    db.commit()

    return record

def predict_all_areas() -> Dict[str, Any]:
    start = time.perf_counter()
    logger.info("Starting flood prediction job")

    db = get_db_session()
    processed = 0
    high_risk = 0
    errors = 0

    try:
        area_ids = get_all_area_ids_with_weather(db)

        for area_id in area_ids:
            try:
                result = predict_realtime_by_area(db, area_id)

                if result.get("status") != "success":
                    errors += 1
                    logger.warning(
                        "Prediction skipped for area_id=%s: %s",
                        area_id,
                        result.get("message"),
                    )
                    continue

                processed += 1

                forecast = result.get("forecast", {})
                has_high_risk = any(
                    day.get("risk_level") == "HIGH"
                    for day in forecast.values()
                )

                if has_high_risk:
                    high_risk += 1

            except Exception:
                errors += 1
                logger.exception("Prediction failed for area_id=%s", area_id)
                db.rollback()

        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "Finished flood prediction job: processed=%s high_risk=%s errors=%s duration_ms=%s",
            processed,
            high_risk,
            errors,
            duration_ms,
        )

        if processed == 0 and errors > 0:
            return {
                "status": "error",
                "processed": processed,
                "high_risk": high_risk,
                "errors": errors,
                "duration_ms": duration_ms,
                "message": "All prediction jobs failed",
            }

        return {
            "status": "success",
            "processed": processed,
            "high_risk": high_risk,
            "errors": errors,
            "duration_ms": duration_ms,
        }
    finally:
        db.close()