from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class OpenAIHTTPException(Exception):
    status_code: int
    message: str
    error_type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "param": self.param,
                "code": self.code,
            }
        }


async def openai_http_exception_handler(_: Request, exc: OpenAIHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = first_error.get("loc", [])
    param = str(location[-1]) if location else None
    message = first_error.get("msg", "Invalid request.")
    payload = OpenAIHTTPException(
        status_code=400,
        message=message,
        error_type="invalid_request_error",
        param=param,
        code="validation_error",
    )
    return JSONResponse(status_code=400, content=payload.to_dict())


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    payload = OpenAIHTTPException(
        status_code=500,
        message=f"Internal server error: {exc}",
        error_type="server_error",
        code="internal_error",
    )
    return JSONResponse(status_code=500, content=payload.to_dict())

