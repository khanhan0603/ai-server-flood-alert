from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION

from app.config.database import Base


class IotSensorReading(Base):
    __tablename__ = "iot_sensor_readings"

    id = Column(String, primary_key=True, index=True)

    device_id = Column(String, ForeignKey("iot_devices.device_id"), nullable=False)

    water_level = Column(DOUBLE_PRECISION, nullable=False)
    status = Column(String, nullable=False)
    is_valid = Column(Boolean, nullable=False)

    recorded_at = Column(DateTime, nullable=False)