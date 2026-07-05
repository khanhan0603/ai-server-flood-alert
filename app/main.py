from fastapi import FastAPI

from app.api.routes.flood_prediction import router as prediction_router
from app.api.routes.benchmark import router as benchmark_router
from app.api.middleware.cors import setup_cors


app = FastAPI(
    title="Flood Alert AI Prediction Service",
    version="1.0.0",
)

setup_cors(app)

app.include_router(prediction_router)
app.include_router(benchmark_router)


@app.get("/health")
def health():
    
    return {"status": "ok"}