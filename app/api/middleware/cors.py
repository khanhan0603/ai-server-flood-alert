from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.database import settings


def setup_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.spring_boot_origin, "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )