import hmac
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class AuthTokenMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Token header against GEOVIZ_API_TOKEN environment variable."""

    async def dispatch(self, request: Request, call_next) -> Response:
        expected_token = os.environ.get("GEOVIZ_API_TOKEN", "")
        if not expected_token:
            # No token configured — deny all to prevent accidental open access
            return JSONResponse(
                status_code=401,
                content={"detail": "API token not configured on server"},
            )

        provided_token = request.headers.get("X-API-Token", "")
        if not provided_token or not hmac.compare_digest(provided_token, expected_token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API token"},
            )

        return await call_next(request)
