from pydantic import BaseModel
from datetime import date

class PredictionRecoveryRequest(BaseModel):
    date: date