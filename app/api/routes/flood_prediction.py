from fastapi import APIRouter, Query
from uuid import UUID
from app.api.services.realtime_flood_service import predict_all_areas, predict_test_areas,recover_test_areas
import time
import logging

from app.api.services.realtime_flood_service import recover_missing_areas
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/predict-batch")
def predict_batch(
    offset: int = Query(0),
    limit: int = Query(500)
):
    print(
        f"PREDICTION START offset={offset} limit={limit}",
        flush=True
    )

    try:
        result = predict_all_areas(
            offset=offset,
            limit=limit
        )

        print(
            f"PREDICTION FINISHED offset={offset} result={result}",
            flush=True
        )

        return result

    except Exception as e:
        import traceback

        traceback.print_exc()

        return {
            "status": "error",
            "message": str(e)
        }
        
from pydantic import BaseModel

class PredictRequest(BaseModel):
    areaIds: list[str]
#Test area
@router.post("/predict-test-batch")
def predict_test_batch(request: PredictRequest):
    return predict_test_areas(request.areaIds)
        
@router.post("/recover-test")
def recover_test(request: PredictRequest):
    return recover_test_areas(request.areaIds)        

# Recovery after predict
@router.post("/recover-missing")
def recover_missing():

    logger.info("START RECOVERY API")

    start = time.perf_counter()

    result = recover_missing_areas()

    logger.info(
        "RECOVERY FINISHED elapsed=%.2fs attempts=%s recovered=%s remaining=%s",
        time.perf_counter() - start,
        result["attempts"],
        result["recovered"],
        result["remaining_missing"],
    )

    return result



