from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.logging import RequestLoggingMiddleware

from app.api.routes.me import router as me_router
from app.api.routes.categories import router as categories_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.budgets import router as budgets_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.stats import router as stats_router
from app.api.routes.fx import router as fx_router

from fastapi.exceptions import RequestValidationError

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(RequestLoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id", "X-Response-Time-Ms"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(me_router)
    app.include_router(categories_router)
    app.include_router(transactions_router)
    app.include_router(budgets_router)
    app.include_router(dashboard_router)
    app.include_router(stats_router)
    app.include_router(fx_router)

    return app


app = create_app()
