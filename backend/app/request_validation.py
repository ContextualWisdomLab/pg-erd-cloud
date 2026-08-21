"""Return secret-safe validation failures for sensitive request bodies."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request
from fastapi.routing import APIRoute
from fastapi.exception_handlers import (
    request_validation_exception_handler as default_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.responses import JSONResponse, Response


def _is_legacy_apply_path(path: str) -> bool:
    """Recognize only the stored-connection legacy apply request path."""

    return path.startswith("/api/connections/") and path.endswith("/apply-sql")


def _is_sensitive_body_path(path: str) -> bool:
    """Recognize endpoints whose rejected bodies must never be reflected."""

    return _is_legacy_apply_path(path) or path == "/api/dbml/convert"


def _sensitive_validation_response() -> JSONResponse:
    """Return the fixed response shared by sensitive-body rejection paths."""

    return JSONResponse(
        status_code=422,
        content={"detail": "request validation failed"},
    )


class SecretSafeLegacyApplyRoute(APIRoute):
    """Validate the sensitive legacy apply body before route dependencies."""

    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        route_handler = super().get_route_handler()

        async def guarded_route_handler(request: Request) -> Response:
            if _is_legacy_apply_path(request.url.path):
                try:
                    payload = await request.json()
                    from app.schemas import ApplySqlIn

                    ApplySqlIn.model_validate(payload)
                except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                    raise
                except (ValidationError, ValueError, TypeError):
                    return _sensitive_validation_response()
            return await route_handler(request)

        return guarded_route_handler


async def request_validation_exception_handler(
    request: Request,
    error: Exception,
) -> Response:
    """Avoid reflecting SQL/DBML while retaining normal validation elsewhere."""

    if _is_sensitive_body_path(request.url.path):
        return _sensitive_validation_response()
    if not isinstance(error, RequestValidationError):
        raise error
    return await default_validation_handler(request, error)
