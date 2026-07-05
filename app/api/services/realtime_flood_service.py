from decimal import Decimal
import os
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
from app.internal.domain.weather_data import WeatherData

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import func


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

# Tạo hàm lấy danh sách area còn thiếu.
def get_missing_area_ids(
    db: Session,
) -> list[str]:

    today = datetime.now(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date()

    all_area_ids = set(
        get_all_area_ids_with_weather(db)
    )

    predicted_area_ids = {
        str(area_id)
        for (area_id,) in (
            db.query(FloodPrediction.area_id)
            .filter(
                func.date(FloodPrediction.predicted_at) == today
            )
            .distinct()
            .all()
        )
    }

    return list(
        all_area_ids - predicted_area_ids
    )

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

    latest_weather = max(weather_records, key=lambda item: item.time)

    feature_result = build_features_from_weather_history(weather_records)

    features = feature_result["features"]

    weather_from = feature_result["weather_from"]
    weather_to = feature_result["weather_to"]

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


from datetime import datetime
from zoneinfo import ZoneInfo

def get_weather_history_by_area(
    db: Session,
    area_id: str,
) -> list[WeatherData]:

    today_vn = datetime.now(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date()

    return (
        db.query(WeatherData)
        .filter(
            WeatherData.area_id == area_id,
            WeatherData.time < today_vn
        )
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

    return {
        "features": features,
        "weather_from": pd.to_datetime(df.iloc[0]["date"]),
        "weather_to": pd.to_datetime(today["date"]),
    }

def save_flood_prediction(
    db: Session,
    weather: WeatherData,
    prediction: Dict[str, Any],
    weather_from,
    weather_to,
) -> FloodPrediction:
    
    today = datetime.now(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date() #Ngày AI chạy

    record = FloodPrediction(
        lead1_probability=prediction["forecast"]["day_1"]["probability"],
        lead2_probability=prediction["forecast"]["day_2"]["probability"],
        lead3_probability=prediction["forecast"]["day_3"]["probability"],

        lead1=prediction["forecast"]["day_1"]["risk_level"],
        lead2=prediction["forecast"]["day_2"]["risk_level"],
        lead3=prediction["forecast"]["day_3"]["risk_level"],
        
        lead1_date=today,
        lead2_date=today + timedelta(days=1),
        lead3_date=today + timedelta(days=2),

        predicted_at=datetime.now(
            ZoneInfo("Asia/Ho_Chi_Minh")
        ),
        weather_from=weather_from,
        weather_to=weather_to,
        area_id=weather.area_id,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    
    print(
        f"SAVED area={weather.area_id} prediction={record.id}",
        flush=True
    )

    return record

# Nó sẽ:
# Lấy danh sách area còn thiếu bằng get_missing_area_ids().
# Chạy lại prediction chỉ cho các area đó.
# Trả về thống kê để sau này log và tạo notification.
def recover_missing_areas() -> Dict[str, int]:
    MAX_RECOVERY_ATTEMPTS = 3 #Retry vá lại dữ liệu tối đa 3 lần

    total_recovered = 0
    total_errors = 0
    logger.info("START RECOVERY")

    db = get_db_session()

    try:
        missing_area_ids = get_missing_area_ids(db)
    finally:
        db.close()

    if not missing_area_ids:
        logger.info("RECOVERY: no missing areas")

        return {
            "attempts": 0,
            "recovered": 0,
            "errors": 0,
            "remaining_missing": 0,
        }

    recovered = 0
    errors = 0

    logger.info(
        "RECOVERY: found %s missing areas",
        len(missing_area_ids),
    )
    attempt_used=0 #số lần retry thực tế
    for attempt in range(1, MAX_RECOVERY_ATTEMPTS + 1):
        attempt_used=attempt
        db = get_db_session()

        try:
            missing_area_ids = get_missing_area_ids(db)
        finally:
            db.close()

        if not missing_area_ids:
            logger.info(
                "RECOVERY SUCCESS after %s attempt(s)",
                attempt - 1,
            )
            break

        logger.info(
            "RECOVERY ATTEMPT %s: %s missing areas",
            attempt,
            len(missing_area_ids),
        )

        recovered = 0
        errors = 0

        for area_id in missing_area_ids:

            try:
                result = _predict_one_area(area_id)

                if result.get("status") == "success":
                    recovered += 1
                else:
                    errors += 1

            except Exception:
                errors += 1

                logger.exception(
                    "Recovery failed area=%s",
                    area_id,
                )

        total_recovered += recovered
        total_errors += errors

    logger.info(
        "RECOVERY FINISHED recovered=%s errors=%s",
        recovered,
        errors,
    )
    #Để admin biết còn thiếu bao nhiêu khu vực chưa predict
    db = get_db_session()

    try:
        final_missing = len(get_missing_area_ids(db))
    finally:
        db.close()
        
    logger.info(
        "RECOVERY COMPLETED: remaining_missing=%s",
        final_missing,
    )
    return {
        "attempts": attempt_used, #số lần retry thực tế
        "recovered": total_recovered, #số khu vực thiếu dữ liệu được vá
        "errors": total_errors, #số lỗi
        "remaining_missing": final_missing, #số khu vực chưa vá dữ liệu
    }

def predict_all_areas(
    offset: int = 0,
    limit: int = 500
    ) -> Dict[str, Any]:
    logger.info("START BACKGROUND PREDICTION")
    start = time.perf_counter()

    db = get_db_session()
    try:
        area_ids = get_all_area_ids_with_weather(db)
        all_total = len(area_ids)
        
        print(
            f"ALL_TOTAL={all_total}, UNIQUE={len(set(area_ids))}",
            flush=True
        )

        area_ids = area_ids[offset: offset + limit]
        
        print(
            f"OFFSET={offset}, LIMIT={limit}, ACTUAL={len(area_ids)}",
            flush=True
        )

        total = len(area_ids)

        print(
            f"OFFSET={offset} "
            f"LIMIT={limit} "
            f"BATCH_SIZE={total} "
            f"ALL_TOTAL={all_total}",
            flush=True
        )
    finally:
        db.close()

    logger.info(
        "Batch offset=%s limit=%s total=%s",
        offset,
        limit,
        total
    )

    processed = 0
    errors = 0
    high_risk = 0

    BATCH_SIZE = 100
    MAX_WORKERS = 3

    for batch_start in range(0, total, BATCH_SIZE):
        batch = area_ids[batch_start: batch_start + BATCH_SIZE]

        logger.info(
            "Starting batch %s -> %s",
            batch_start + 1,
            min(batch_start + BATCH_SIZE, total)
        )

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

            futures = {
                executor.submit(_predict_one_area, area_id): area_id
                for area_id in batch
            }

            for future in as_completed(futures):
                area_id = futures[future]

                try:
                    result = future.result()
                    
                    if result.get("status") != "success":
                        print(
                            f"SKIP area={area_id} reason={result}",
                            flush=True
                        )

                    if result.get("status") == "success":
                        processed += 1

                        if any(
                            day.get("risk_level") == "HIGH"
                            for day in result.get("forecast", {}).values()
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

                    logger.exception(
                        "Prediction failed area=%s",
                        area_id
                    )

        print(
            f"PID={os.getpid()} "
            f"PROGRESS={processed + errors}/{total} "
            f"processed={processed} "
            f"errors={errors}",
            flush=True
        )

    duration_ms = int((time.perf_counter() - start) * 1000)

    logger.info(
        "Finished: total=%s processed=%s high_risk=%s errors=%s duration_ms=%s",
        total,
        processed,
        high_risk,
        errors,
        duration_ms,
    )

    # Kiểm tra thực tế trong DB có bao nhiêu area đã được lưu hôm nay
    db = get_db_session()

    try:
        today = datetime.now(
            ZoneInfo("Asia/Ho_Chi_Minh")
        ).date()

        actual = (
            db.query(FloodPrediction.area_id)
            .filter(func.date(FloodPrediction.predicted_at) == today)
            .distinct()
            .count()
        )

        print(
            f"ACTUAL DB TODAY = {actual}",
            flush=True
        )

    finally:
        db.close()
        
    # Sau khi predict_all_areas() chạy xong, tự động chạy recovery 1 lần.
    recovery_result = recover_missing_areas()

    logger.info(
        "Recovery summary: attempts=%s recovered=%s errors=%s remaining_missing=%s",
        recovery_result["attempts"],
        recovery_result["recovered"],
        recovery_result["errors"],
        recovery_result["remaining_missing"],
    )

    return {
        "status": "success",
        "total": total,
        "processed": processed,
        "high_risk": high_risk,
        "errors": errors,
        "duration_ms": duration_ms,
        "recovery": recovery_result,
    }

def _predict_one_area(area_id: str) -> Dict[str, Any]:
    print(f"START AREA {area_id}", flush=True)

    db = get_db_session()

    try:
        result = predict_realtime_by_area(db, area_id)

        print(f"DONE AREA {area_id}", flush=True)

        return result

    except Exception:
        import traceback
        traceback.print_exc()
        raise

    finally:
        db.close()
        
        
#Hàm để recovery cơ sở dữ liệu ngày còn thiếu
def recover_prediction_by_datetime(
    predicted_at: datetime,
) -> Dict[str, Any]:
    
    target_date = predicted_at.astimezone(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date()

    logger.info(
        "START MANUAL RECOVERY predicted_at=%s",
        predicted_at,
    )

    db = get_db_session()

    try:
        missing_area_ids = get_missing_area_ids_by_datetime(
            db,
            predicted_at,
        )
    finally:
        db.close()

    if not missing_area_ids:
        return {
            "status": "success",
            "target_date": target_date.isoformat(),
            "missing": 0,
            "recovered": 0,
            "errors": 0,
        }

    recovered = 0
    errors = 0

    logger.info(
        "MANUAL RECOVERY: found %s missing areas",
        len(missing_area_ids),
    )

    for area_id in missing_area_ids:

        try:
            db = get_db_session()

            try:
                result = predict_realtime_by_area_with_datetime(
                    db,
                    area_id,
                    predicted_at,
                )
            finally:
                db.close()

            if result.get("status") == "success":
                recovered += 1
            else:
                errors += 1

        except Exception:
            errors += 1

            logger.exception(
                "Manual recovery failed area=%s",
                area_id,
            )

    logger.info(
        "MANUAL RECOVERY FINISHED recovered=%s errors=%s",
        recovered,
        errors,
    )

    return {
        "status": "success",
        "predicted_at": predicted_at.isoformat(),
        "missing": len(missing_area_ids),
        "recovered": recovered,
        "errors": errors,
    }
    
from datetime import timezone
def get_missing_area_ids_by_datetime(
    db: Session,
    predicted_at: datetime,
) -> list[str]:
    
    local_time = predicted_at.astimezone(
        ZoneInfo("Asia/Ho_Chi_Minh")
    )

    is_morning = local_time.hour < 12

    predicted_at = predicted_at.astimezone(timezone.utc)

    # Snapshot sáng: 06:30 -> trước 18:30
    if is_morning:
    # Job sáng (UTC 23:30 hôm trước -> 11:30 hôm nay)
        window_start = predicted_at.replace(
            hour=23,
            minute=30,
            second=0,
            microsecond=0,
        )

        window_end = window_start + timedelta(hours=12)

    else:
        # Job tối (UTC 11:30 -> 23:30 cùng ngày)
        window_start = predicted_at.replace(
            hour=11,
            minute=30,
            second=0,
            microsecond=0,
        )

        window_end = window_start + timedelta(hours=12)

    all_area_ids = set(
        get_all_area_ids_with_weather(db)
    )

    predicted_area_ids = {
        str(area_id)
        for (area_id,) in (
            db.query(FloodPrediction.area_id)
            .filter(
                FloodPrediction.predicted_at >= window_start.replace(tzinfo=None),
                FloodPrediction.predicted_at < window_end.replace(tzinfo=None),
            )
            .distinct()
            .all()
        )
    }

    return list(all_area_ids - predicted_area_ids)
    
def save_flood_prediction_by_datetime(
    db: Session,
    weather: WeatherData,
    prediction: Dict[str, Any],
    weather_from,
    weather_to,
    predicted_at: datetime,
) -> FloodPrediction:

    today = predicted_at.astimezone(
        ZoneInfo("Asia/Ho_Chi_Minh")
    ).date()

    record = FloodPrediction(
        lead1_probability=prediction["forecast"]["day_1"]["probability"],
        lead2_probability=prediction["forecast"]["day_2"]["probability"],
        lead3_probability=prediction["forecast"]["day_3"]["probability"],

        lead1=prediction["forecast"]["day_1"]["risk_level"],
        lead2=prediction["forecast"]["day_2"]["risk_level"],
        lead3=prediction["forecast"]["day_3"]["risk_level"],

        lead1_date=today,
        lead2_date=today + timedelta(days=1),
        lead3_date=today + timedelta(days=2),

        predicted_at=predicted_at,

        weather_from=weather_from,
        weather_to=weather_to,
        area_id=weather.area_id,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    print(
        f"RECOVERY SAVED area={weather.area_id} prediction={record.id}",
        flush=True,
    )

    return record

def predict_realtime_by_area_with_datetime(
    db: Session,
    area_id: str,
    predicted_at: datetime,
) -> Dict[str, Any]:

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

    latest_weather = max(weather_records, key=lambda item: item.time)

    feature_result = build_features_from_weather_history(weather_records)

    features = feature_result["features"]

    weather_from = feature_result["weather_from"]
    weather_to = feature_result["weather_to"]

    payload = {
        "province": area_id,
        "area_id": area_id,
        "lat": None,
        "lon": None,
    }
    payload.update(features)

    prediction = run_flood_prediction(payload)

    saved_prediction = save_flood_prediction_by_datetime(
        db,
        latest_weather,
        prediction,
        weather_from,
        weather_to,
        predicted_at,
    )

    prediction["status"] = "success"
    prediction["source"] = "ai_weather_model"
    prediction["area_id"] = area_id
    prediction["iot_available"] = False
    prediction["weather_time"] = (
        latest_weather.time.isoformat()
        if latest_weather.time
        else None
    )
    prediction["weather_records_used"] = len(weather_records)

    prediction["prediction_id"] = str(saved_prediction.id)
    prediction["predicted_at"] = saved_prediction.predicted_at.isoformat()

    return prediction