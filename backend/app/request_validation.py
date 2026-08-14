"""Return secret-safe validation failures for sensitive request bodies."""

from fastapi import Request
from fastapi.exception_handlers import (
    request_validation_exception_handler as default_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse, Response


def _is_legacy_apply_path(path: str) -> bool:
    """Recognize only the stored-connection legacy apply request path."""

    return path.startswith("/api/connections/") and path.endswith("/apply-sql")


async def request_validation_exception_handler(
    request: Request,
    error: Exception,
) -> Response:
    """Avoid reflecting legacy SQL while retaining normal validation elsewhere."""

    if _is_legacy_apply_path(request.url.path):
        return JSONResponse(
            status_code=422,
            content={"detail": "request validation failed"},
        )
    if not isinstance(error, RequestValidationError):
        raise error
    return await default_validation_handler(request, error)
