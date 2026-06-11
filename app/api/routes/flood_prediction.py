from fastapi import APIRouter, BackgroundTasks
import asyncio
from app.api.services.realtime_flood_service import predict_all_areas

router = APIRouter()

prediction_status = {"running": False, "last_result": None}


@router.post("/predict-all/async")
def predict_all(background_tasks: BackgroundTasks):
    if prediction_status["running"]:
        return {"status": "already_running"}

    background_tasks.add_task(run_predict_all_background)
    return {"status": "started"}


@router.get("/predict-all/status")
def predict_all_status():
    return prediction_status


def run_predict_all_background():
    # Hàm sync — BackgroundTasks chạy trong thread riêng, không block event loop
    prediction_status["running"] = True
    try:
        result = predict_all_areas()
        prediction_status["last_result"] = result
    except Exception as e:
        prediction_status["last_result"] = {"status": "error", "message": str(e)}
    finally:
        prediction_status["running"] = False