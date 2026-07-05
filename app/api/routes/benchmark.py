from fastapi import APIRouter
from app.api.services.benchmark_service import get_all_events
from app.api.services.benchmark_service import generate_grid_points
from app.api.services.benchmark_service import run_event
from app.api.services.benchmark_service import test_dataframe
from fastapi import APIRouter, Query
from app.api.services.benchmark_service import benchmark_event

from app.api.services.benchmark_service import (
    benchmark_province,
)

router = APIRouter()

router = APIRouter(
    prefix="/benchmark",
    tags=["Benchmark"]
)

from app.api.services.benchmark_service import benchmark_event
from app.api.services.benchmark_events import BENCHMARK_EVENTS

@router.get("/events/run-all")
def benchmark_all_events():
    results = []

    for event in BENCHMARK_EVENTS:
        print(f"===== {event['id']} - {event['name']} =====")

        try:
            benchmark_event(event["id"])

            results.append({
                "event_id": event["id"],
                "event_name": event["name"],
                "status": "done",
            })

        except Exception as e:
            print(e)

            results.append({
                "event_id": event["id"],
                "event_name": event["name"],
                "status": "failed",
                "message": str(e),
            })

    return {
        "status": "completed",
        "total_events": len(BENCHMARK_EVENTS),
        "success": sum(1 for r in results if r["status"] == "done"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }

@router.get("/events")
def events():
    return get_all_events()

@router.get("/events/{event_id}")
def evaluate_event(event_id: str):
    return run_event(event_id)

@router.get("/grid/{province}")
def test_grid(province: str):
    points = generate_grid_points(province)

    return {
        "province": province,
        "total_points": len(points),
        "sample": points[:10]
    }

@router.get("/dataframe")
def dataframe():
    return test_dataframe()

@router.get("/province")
def benchmark_one_province(
    province: str = Query(...),
    target_date: str = Query(...),
    limit: int | None = Query(None),
):
    return benchmark_province(
        province=province,
        target_date=target_date,
        limit=limit,
    )



@router.get("/event/{event_id}")
def benchmark_one_event(event_id: str):
    return benchmark_event(event_id)

