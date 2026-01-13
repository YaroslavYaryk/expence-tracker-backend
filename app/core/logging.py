import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        ms = int((time.time() - start) * 1000)

        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(ms)
        return response
