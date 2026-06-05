from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION

from app.config.database import Base


class IotDevice(Base):
    __tablename__ = "iot_devices"

    device_id = Column(String, primary_key=True, index=True)

    area_id = Column(String, ForeignKey("areas.area_id"), nullable=False)

    ten_thietbi = Column(String, nullable=True)

    lat = Column(Numeric(10, 7), nullable=False)
    lon = Column(Numeric(10, 7), nullable=False)

    nguong_canh_bao = Column(DOUBLE_PRECISION, nullable=True)
    trang_thai = Column(String, nullable=False)

    last_seen_at = Column(DateTime, nullable=True)

    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)