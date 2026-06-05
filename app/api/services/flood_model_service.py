from datetime import datetime
from pathlib import Path
from typing import Any,Dict

import joblib
import numpy as np

BASE_DIR=Path(__file__).resolve().parents[2]
MODEL_DIR=BASE_DIR / "models"

models={
    lead: joblib.load(MODEL_DIR / f"xgboost_lead{lead}d.pkl")
    for lead in [1,2,3]
}

FEATURES=joblib.load(MODEL_DIR / "feature_cols.pkl")
THRESHOLD=float(joblib.load(MODEL_DIR / "optimal_threshold.pkl"))

RISK_META={
    "HIGH":{"color":"red","emoji":"🔴"},
    "MEDIUM":{"color":"yellow","emoji":"🟡"},
    "LOW":{"color":"green","emoji":"🟢"},
}

def prob_to_risk(prob:float)->str:
    if prob >= THRESHOLD * 1.8:
        return "HIGH"
    elif prob >= THRESHOLD:
        return "MEDIUM"
    return "LOW"

def run_flood_prediction(payload: Dict[str,Any])-> Dict[str,Any]:
    province=payload.get("province","Unknown")
    lat=payload.get("lat",0.0)
    lon=payload.get("lon",0.0)
    
    vec=[]
    missing=[]
    
    for feat in FEATURES:
        val=payload.get(feat)
        
        try:
            is_nan=np.isnan(val)
        except TypeError:
            is_nan=False
            
        if val is None or is_nan:
            val=0.0
            missing.append(feat)
            
        vec.append(float(val))
        
    X=np.array(vec).reshape(1,-1)
    forecast={}
    
    for lead,model in models.items():
        prob=float(model.predict_proba(X)[0,1])
        risk=prob_to_risk(prob)
        
        forecast[f"day_{lead}"]={
            "lead_days":lead,
            "probability":round(prob,4),
            "risk_level":risk,
            "alert":prob >= THRESHOLD,
            "color":RISK_META[risk]["color"],
        }
    max_prob=max(v["probability"] for v in forecast.values())
    overall_risk=prob_to_risk(max_prob)
    meta=RISK_META[overall_risk]
    
    return {
        "timestamp":datetime.now().isoformat(),
        "province":province,
        "lat":lat,
        "lon":lon,
        "overall_risk":overall_risk,
        "color":meta["color"],
        "emoji":meta["emoji"],
        "probability":round(max_prob,4),
        "threshold":THRESHOLD,
        "features_used":len(FEATURES)-len(missing),
        "missing_features":missing,
        "forecast":forecast
    }
    
def get_model_features()-> Dict[str,Any]:
    return {
        "total":len(FEATURES),
        "features":list(FEATURES),
    }
    
def get_model_features() -> Dict[str, Any]:
    return {
        "total": len(FEATURES),
        "features": list(FEATURES),
    }


def get_model_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "features": len(FEATURES),
        "threshold": THRESHOLD,
        "models": ["lead1d", "lead2d", "lead3d"],
    }