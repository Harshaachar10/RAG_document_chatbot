from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import get_repository
from app.api.router import api_router
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_tags=[
            {"name": "health", "description": "Health and reference data"},
            {"name": "dashboard", "description": "Overview metrics"},
            {"name": "doctors", "description": "Golden doctor profiles"},
            {"name": "reviews", "description": "Review center"},
            {"name": "sources", "description": "Source records"},
            {"name": "evidence", "description": "Evidence and documents"},
            {"name": "demo-runs", "description": "Processing simulation"},
            {"name": "quality", "description": "Quality and activity"},
            {"name": "exports", "description": "CSV exports"},
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    def error_body(code: str, message: str, request_id: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "error": {"code": code, "message": message, "details": details or {}},
            "request_id": request_id,
        }

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, request_id, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=422,
            content=error_body(
                "VALIDATION_ERROR",
                "Request validation failed.",
                request_id,
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
        )

    @app.on_event("startup")
    def on_startup() -> None:
        # Initialize CSV repo + runtime state
        get_repository()

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
