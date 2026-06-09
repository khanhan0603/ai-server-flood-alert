from fastapi import APIRouter

from app.api.services.realtime_flood_service import predict_all_areas
from fastapi import BackgroundTasks

router = APIRouter()


@router.post("/predict-all")
def predict_all(background_tasks: BackgroundTasks):
    
    background_tasks.add_task(predict_all_areas)
    return {
        "message":"Prediction started"
    }