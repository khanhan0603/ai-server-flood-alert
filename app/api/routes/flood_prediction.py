from fastapi import APIRouter, Query
from app.api.services.realtime_flood_service import predict_all_areas

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