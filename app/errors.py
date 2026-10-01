"""Consistent error responses: every error body has a human-readable ``detail`` string.

Validation errors additionally carry ``errors: [{field, message}]`` so the frontend can
show messages inline next to the offending input.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str, field: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        self.field = field
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND


class ValidationFailed(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT


def _humanize(field: str) -> str:
    text = field.replace("_id", "").replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _friendly_message(err: dict[str, Any], field: str | None) -> str:
    label = _humanize(field) if field else "Value"
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    if kind == "missing":
        return f"{label} is required"
    if kind == "greater_than_equal" and str(ctx.get("ge")) == "0":
        return f"{label} cannot be negative"
    if kind == "greater_than" and str(ctx.get("gt")) == "0":
        return f"{label} must be greater than zero"
    if kind == "string_too_short":
        return f"{label} is required"
    if kind in {"enum", "literal_error"}:
        return f"{label} has an invalid value"
    msg = err.get("msg", "Invalid value")
    return f"{label}: {msg[:1].lower() + msg[1:]}"


def _field_from_loc(loc: tuple[Any, ...]) -> str | None:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    # Drop pydantic's union/function wrappers such as "function-after[...]".
    parts = [p for p in parts if not p.startswith(("function-", "constrained-"))]
    return parts[0] if parts else None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        body: dict[str, Any] = {"detail": exc.detail}
        if exc.field:
            body["errors"] = [{"field": exc.field, "message": exc.detail}]
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            field = _field_from_loc(tuple(err.get("loc", ())))
            errors.append({"field": field, "message": _friendly_message(err, field)})
        detail = errors[0]["message"] if errors else "Invalid request"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail, "errors": errors}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)
