from datetime import datetime
from pydantic import BaseModel

class PredictionRecoveryRequest(BaseModel):
    predicted_at: datetime