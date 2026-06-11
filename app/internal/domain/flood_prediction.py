import uuid

from sqlalchemy import Column, Date, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base


class FloodPrediction(Base):
    __tablename__ = "flood_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    lead1 = Column(String, nullable=True)
    lead2 = Column(String, nullable=True)
    lead3 = Column(String, nullable=True)
    
    lead1_probability = Column(Float)
    lead2_probability = Column(Float)
    lead3_probability = Column(Float)
    
    lead1_date=Column(Date, nullable=True)
    lead2_date=Column(Date, nullable=True)
    lead3_date=Column(Date, nullable=True)

    predicted_at = Column(DateTime, nullable=True)
    weather_from = Column(DateTime, nullable=True)
    weather_to = Column(DateTime, nullable=True)

    area_id = Column(UUID(as_uuid=True), nullable=True)
    sensor_reading_id = Column(UUID(as_uuid=True), nullable=True)