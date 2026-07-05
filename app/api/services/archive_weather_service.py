# app/api/services/archive_weather_service.py

from typing import Dict, Any
import math                          # ← thiếu cái này
import time
import requests
import pandas as pd
import numpy as np
from app.internal.domain.weather_data import WeatherData

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

session = requests.Session()


def load_archive_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:

    start = start_date.replace("-", "")
    end   = end_date.replace("-", "")

    params = {
        "parameters": "PRECTOTCORR,T2M,T2MDEW,PS,WS10M,WD10M,RH2M",
        "community":  "RE",
        "longitude":  lon,
        "latitude":   lat,
        "start":      start,
        "end":        end,
        "format":     "JSON",
        "time-standard": "LST",
    }

    max_retries = 5

    for attempt in range(max_retries):
        try:
            response = session.get(
                NASA_POWER_URL,
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait = 5 * (2 ** attempt)
            print(f"Retry {attempt+1}: {e}, wait {wait}s...")
            time.sleep(wait)

    raise RuntimeError("NASA POWER API failed after max retries")


def _calc_et0_hargreaves(
    t_mean: float,
    t_max: float,
    t_min: float,
    lat_rad: float,
    doy: int,
) -> float:
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    declination = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(-math.tan(lat_rad) * math.tan(declination))
    Ra = (24 * 60 / math.pi) * 0.082 * dr * (
        ws * math.sin(lat_rad) * math.sin(declination)
        + math.cos(lat_rad) * math.cos(declination) * math.sin(ws)
    )
    et0 = 0.0023 * Ra * (t_mean + 17.8) * max((t_max - t_min), 0) ** 0.5
    return max(float(et0), 0.0)


def archive_to_dataframe(data: dict, lat: float = 0.0) -> pd.DataFrame:

    props = data["properties"]["parameter"]

    time_keys = None
    for var in ["T2M", "PRECTOTCORR", "T2MDEW", "PS", "WS10M", "WD10M", "RH2M"]:
        val = props.get(var)
        if isinstance(val, dict) and len(val) > 0:
            time_keys = sorted(val.keys())
            time_keys = [k for k in time_keys if len(k) == 10 and k.isdigit()]
            break

    if not time_keys:
        return pd.DataFrame(columns=[
            "time", "precipitation", "temperature_2m", "dew_point_2m",
            "surface_pressure", "wind_speed_10m", "wind_direction_10m",
            "relative_humidity_2m", "et0_fao_evapotranspiration"
        ])

    def safe_get(var_name, key):
        d = props.get(var_name)
        if not isinstance(d, dict):
            return 0.0
        v = d.get(key)
        if v is None or v == -999.0:
            return 0.0
        return float(v)

    lat_rad = math.radians(lat)

    temp_by_day = {}
    for k in time_keys:
        day = k[:8]
        t = safe_get("T2M", k)
        if day not in temp_by_day:
            temp_by_day[day] = []
        temp_by_day[day].append(t)

    et0_by_hour = {}
    for k in time_keys:
        day = k[:8]
        temps = temp_by_day[day]
        doy = pd.to_datetime(day, format="%Y%m%d").day_of_year
        et0_daily = _calc_et0_hargreaves(
            t_mean=float(np.mean(temps)),
            t_max=float(np.max(temps)),
            t_min=float(np.min(temps)),
            lat_rad=lat_rad,
            doy=doy,
        )
        et0_by_hour[k] = et0_daily / 24.0

    times = pd.to_datetime(time_keys, format="%Y%m%d%H")

    df = pd.DataFrame({
        "time":                       times,
        "precipitation":              [safe_get("PRECTOTCORR", k)    for k in time_keys],
        "temperature_2m":             [safe_get("T2M", k)            for k in time_keys],
        "dew_point_2m":               [safe_get("T2MDEW", k)         for k in time_keys],
        "surface_pressure":           [safe_get("PS", k) * 10        for k in time_keys],
        "wind_speed_10m":             [safe_get("WS10M", k)          for k in time_keys],
        "wind_direction_10m":         [safe_get("WD10M", k)          for k in time_keys],
        "relative_humidity_2m":       [safe_get("RH2M", k)           for k in time_keys],
        "et0_fao_evapotranspiration": [et0_by_hour[k]                for k in time_keys],
    })

    return df


def dataframe_to_weather_records(df: pd.DataFrame):
    records = []

    for _, row in df.iterrows():
        item = WeatherData()
        item.time               = row["time"]
        item.rainfall           = row["precipitation"]
        item.temperature        = row["temperature_2m"]
        item.dewpoint           = row["dew_point_2m"]
        item.pressure           = row["surface_pressure"]
        item.wind_speed         = row["wind_speed_10m"]
        item.wind_direction     = row["wind_direction_10m"]
        item.humidity           = row["relative_humidity_2m"]
        item.evapotranspiration = row["et0_fao_evapotranspiration"]
        records.append(item)

    return records