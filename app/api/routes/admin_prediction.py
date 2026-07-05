from fastapi import APIRouter

from app.api.request.recovery_request import (
    PredictionRecoveryRequest,
)
from app.api.services.realtime_flood_service import (
    recover_prediction_by_date,
)

router = APIRouter(
    prefix="/admin/predictions",
    tags=["Admin Prediction"],
)


@router.post("/recovery")
def recovery_prediction(
    request: PredictionRecoveryRequest,
):
    return recover_prediction_by_date(
        request.date,
    )