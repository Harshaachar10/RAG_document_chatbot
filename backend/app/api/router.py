from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    ai,
    ask,
    cleanup,
    dashboard,
    doctors,
    evidence,
    exports,
    health,
    notes,
    payments,
    quality,
    reviews,
    runs,
    sources,
    uploads,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(doctors.router)
api_router.include_router(reviews.router)
api_router.include_router(sources.router)
api_router.include_router(evidence.router)
api_router.include_router(runs.router)
api_router.include_router(quality.router)
api_router.include_router(exports.router)
api_router.include_router(ai.router)
api_router.include_router(payments.router)
api_router.include_router(notes.router)
api_router.include_router(uploads.router)
api_router.include_router(cleanup.router)
api_router.include_router(ask.router)
