from fastapi import APIRouter

from app.api.services.realtime_flood_service import predict_all_areas


router = APIRouter()


@router.post("/predict-all")
def predict_all():
    
    return predict_all_areas()