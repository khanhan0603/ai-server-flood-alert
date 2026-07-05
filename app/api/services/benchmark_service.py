from app.api.services.benchmark_events import BENCHMARK_EVENTS
from app.config.region import REGION_MAP
from app.config.province import PROVINCES
from datetime import datetime, timedelta
import time
import numpy as np
from app.api.services.archive_weather_service import (
    load_archive_weather,
    archive_to_dataframe,
    dataframe_to_weather_records,
)

from app.api.services.realtime_flood_service import (
    build_features_from_weather_history,
)

from app.api.services.realtime_flood_service import run_flood_prediction
from app.config.test_points import TEST_POINTS

def get_all_events():
    return {
        "province": "ha_tinh",
        "bounds": get_province_bounds("ha_tinh")
    }
    
def get_event(event_id: str) -> dict:
    for event in BENCHMARK_EVENTS:
        if event["id"] == event_id:
            return {
                **event,
                "provinces": expand_provinces(event)
            }

    raise ValueError(f"Event {event_id} not found")

def expand_provinces(event: dict) -> list[str]:
    provinces = set(event.get("provinces", []))

    for region in event.get("regions", []):
        provinces.update(REGION_MAP.get(region, []))

    return sorted(provinces)

# Hàm sinh các ngày cần đánh giá của một event
def generate_event_dates(event: dict) -> list[str]:
    start = datetime.strptime(event["start"], "%Y-%m-%d").date()
    end = datetime.strptime(event["end"], "%Y-%m-%d").date()

    dates = []

    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    return dates

def run_event(event_id: str):
    event = get_event(event_id)

    results = []

    for date in generate_event_dates(event):
        for province in event["provinces"]:
            results.append({
                "date": date,
                "province": province
            })

    return {
        "event": event["name"],
        "total_tasks": len(results),
        "tasks": results
    }
    
def get_province_bounds(province: str) -> tuple[float, float, float, float]:
    bounds = PROVINCES.get(province)

    if bounds is None:
        raise ValueError(f"Province '{province}' not found.")

    return bounds

import math
import json
from pathlib import Path

# ── Grid snapping ──────────────────────────────────────────────────────
def generate_grid_points(province: str, step: float = 0.1):
    lat_min, lat_max, lon_min, lon_max = PROVINCES[province]

    def snap_ceil(v: float) -> float:
        return math.ceil(round(v / step, 6)) * step

    lat_start = snap_ceil(lat_min)
    lon_start = snap_ceil(lon_min)

    points = []

    lat = lat_start
    while lat <= lat_max + 1e-9:
        lon = lon_start
        while lon <= lon_max + 1e-9:
            points.append((round(lat, 4), round(lon, 4)))
            lon += step
        lat += step

    return points


# ── Point-level cache (theo ngày) ─────────────────────────────────────
def _point_cache_path(date: str) -> Path:
    return Path("benchmark_results/point_cache") / f"{date}.json"

def _load_point_cache(date: str) -> dict:
    path = _point_cache_path(date)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_point_cache(date: str, cache: dict):
    path = _point_cache_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

def _point_key(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"

def test_dataframe(
    lat: float = 18.35,
    lon: float = 105.90,
    start_date: str = "2025-08-17",
    end_date: str = "2025-08-24",
    province: str = "ha_tinh",
):
    raw = load_archive_weather(lat, lon, start_date, end_date)
    df = archive_to_dataframe(raw, lat=lat)
    records = dataframe_to_weather_records(df)
    feature_result = build_features_from_weather_history(records)
    features = feature_result["features"]

    payload = {
        "province": province,
        "lat": lat,
        "lon": lon,
    }
    payload.update(features)

    prediction = run_flood_prediction(payload)

    return {
        "status": "success",
        "weather_from": str(feature_result["weather_from"]),
        "weather_to": str(feature_result["weather_to"]),
        "prediction": prediction,
    }


def predict_one_point(
    province: str,
    lat: float,
    lon: float,
    target_date: str,
):
    end = datetime.strptime(target_date, "%Y-%m-%d").date()
    start = end - timedelta(days=7)

    raw = load_archive_weather(
        lat=lat,
        lon=lon,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )

    df = archive_to_dataframe(raw, lat=lat)
    records = dataframe_to_weather_records(df)
    feature_result = build_features_from_weather_history(records)

    payload = {
        "province": province,
        "lat": lat,
        "lon": lon,
    }
    payload.update(feature_result["features"])

    prediction = run_flood_prediction(payload)
    prediction["benchmark_date"] = target_date

    return prediction

# ── benchmark_province: dùng point cache thay vì luôn gọi API ─────────
def benchmark_province(
    province: str,
    target_date: str,
    limit: int | None = None,
    point_cache: dict | None = None,
):
    points = generate_grid_points(province)

    if limit is not None:
        points = points[:limit]

    owns_cache = point_cache is None
    if owns_cache:
        point_cache = _load_point_cache(target_date)

    results = []
    high = medium = low = 0
    max_probability = 0.0

    print(f"Start benchmark {province}: {len(points)} points")

    for i, (lat, lon) in enumerate(points, start=1):
        name = f"Point {i}"
        key = _point_key(lat, lon)

        if key in point_cache:
            print(f"[{i}/{len(points)}] {name} ({lat}, {lon}) - cached")
            prediction = point_cache[key]
        else:
            print(f"[{i}/{len(points)}] {name} ({lat}, {lon})")
            prediction = predict_one_point(
                province=province,
                lat=lat,
                lon=lon,
                target_date=target_date,
            )
            time.sleep(0.5)
            point_cache[key] = prediction

        risk = prediction["overall_risk"]
        if risk == "HIGH":
            high += 1
        elif risk == "MEDIUM":
            medium += 1
        else:
            low += 1

        max_probability = max(max_probability, prediction["probability"])

        results.append({
            "name": name,
            "lat": lat,
            "lon": lon,
            "prediction": prediction,
        })

    if owns_cache:
        _save_point_cache(target_date, point_cache)

    return {
        "province": province,
        "benchmark_date": target_date,
        "total_points": len(points),
        "high": high,
        "medium": medium,
        "low": low,
        "max_probability": round(max_probability, 4),
        "results": results,
    }


# ── benchmark_event: chia sẻ point_cache theo ngày giữa các tỉnh ──────
def benchmark_event(
    event_id: str,
    suffix: str = "",
    target_date_override: str = None,
    province_override: list = None,   # ← thêm
):
    output_file = Path(f"benchmark_results/{event_id}{suffix}.json")
    partial_dir = Path(f"benchmark_results/{event_id}{suffix}_partial")
    partial_dir.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        print(f"Skip {event_id}{suffix}: already exists")
        with output_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    event = get_event(event_id)
    results = []

    print(f"=== Benchmark {event['name']}{' ' + suffix if suffix else ''} ===")

    if target_date_override:
        dates = [target_date_override]
    else:
        dates = generate_event_dates(event)

    # ← dùng province_override nếu có, không thì dùng event["provinces"]
    provinces = province_override or event["provinces"]

    for date in dates:
        print(f"Date: {date}")
        point_cache = _load_point_cache(date)

        for province in provinces:   # ← đổi từ event["provinces"] → provinces
            part_file = partial_dir / f"{date}_{province}.json"

            if part_file.exists():
                print(f"Skip {province} on {date}: already done")
                with part_file.open("r", encoding="utf-8") as f:
                    province_result = json.load(f)
            else:
                print(f"Province: {province}")
                province_result = benchmark_province(
                    province=province,
                    target_date=date,
                    limit=None,
                    point_cache=point_cache,
                )
                with part_file.open("w", encoding="utf-8") as f:
                    json.dump(province_result, f, indent=2, ensure_ascii=False)

                _save_point_cache(date, point_cache)

            results.append({
                "date":     date,
                "province": province,
                "summary":  province_result,
            })

    benchmark_result = {
        "event_id":    event["id"],
        "event_name":  event["name"],
        "type":        suffix.strip("_") if suffix else "event",
        "start":       event["start"],
        "end":         event["end"],
        "target_date": target_date_override,
        "generated_at": datetime.now().isoformat(),
        "total_tasks": len(results),
        "results":     results,
    }

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(benchmark_result, f, indent=4, ensure_ascii=False)

    print(f"Saved {output_file}")
    return benchmark_result


def benchmark_all_events():
    results = []

    for event in BENCHMARK_EVENTS:
        eid = event["id"]
        print(f"===== {eid} - {event['name']} =====")

        try:
            # 1. Event chính
            benchmark_event(eid)

            # 2. Neg before
            if event.get("neg_before_date"):
                print(f"===== {eid}_neg_before =====")
                benchmark_event(
                    eid,
                    suffix="_neg_before",
                    target_date_override=event["neg_before_date"],
                )

            # 3. Neg after
            if event.get("neg_after_date"):
                print(f"===== {eid}_neg_after =====")
                benchmark_event(
                    eid,
                    suffix="_neg_after",
                    target_date_override=event["neg_after_date"],
                )

            # 4. Neg spatial — dùng tỉnh khác không bị lũ
            if event.get("neg_spatial_provinces"):
                print(f"===== {eid}_neg_spatial =====")
                benchmark_event(
                    eid,
                    suffix="_neg_spatial",
                    province_override=event["neg_spatial_provinces"],  # ← tỉnh khác
                )

            results.append({
                "event_id":   eid,
                "event_name": event["name"],
                "status":     "done",
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append({
                "event_id":   eid,
                "event_name": event["name"],
                "status":     "failed",
                "message":    str(e),
            })

    return {
        "status":       "completed",
        "total_events": len(BENCHMARK_EVENTS),
        "success":      sum(1 for r in results if r["status"] == "done"),
        "failed":       sum(1 for r in results if r["status"] == "failed"),
        "results":      results,
    }