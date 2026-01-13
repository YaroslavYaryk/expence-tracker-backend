import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: list | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


def get_request_id(request: Request) -> str:
    rid = request.headers.get("x-request-id")
    return rid if rid else str(uuid.uuid4())


async def app_error_handler(request: Request, exc: AppError):
    request_id = getattr(request.state, "request_id", None) or get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "requestId": request_id,
            }
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None) or get_request_id(request)
    details = []
    for e in exc.errors():
        loc = ".".join([str(x) for x in e.get("loc", []) if x != "body"])
        details.append({"field": loc or "body", "issue": e.get("msg", "Invalid")})
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": details,
                "requestId": request_id,
            }
        },
    )
