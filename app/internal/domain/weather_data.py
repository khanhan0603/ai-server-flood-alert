from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint

from app.config.database import Base


class WeatherData(Base):
    __tablename__ = "weather_datas"

    __table_args__ = (
        UniqueConstraint("area_id", "time", name="uk_area_id_time"),
    )

    id = Column(String, primary_key=True, index=True)

    rainfall = Column(Numeric(10, 2), nullable=True)
    temperature = Column(Numeric(10, 2), nullable=True)
    dewpoint = Column(Numeric(10, 2), nullable=True)
    pressure = Column(Numeric(10, 2), nullable=True)
    wind_speed = Column(Numeric(10, 2), nullable=True)
    wind_direction = Column(Numeric(10, 2), nullable=True)
    humidity = Column(Numeric(10, 2), nullable=True)
    evapotranspiration = Column(Numeric(10, 2), nullable=True)

    time = Column(DateTime, nullable=True)

    area_id = Column(String, ForeignKey("areas.area_id"), nullable=False)