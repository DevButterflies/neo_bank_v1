"""Canon enforcement + audit middleware."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bank.orchestrator.governance.config import settings

logger = logging.getLogger("orchestrator.audit")


class AuditAndCanonEnforcementMiddleware(BaseHTTPMiddleware):
    """Logs every API call and attaches the current canon version.

    Every mutating (non-GET) request is checked: if the current canon is not
    ratified and enforcement is enabled, reject the mutation (governance gate).
    """

    WHITELIST_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/health")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())
        start = time.time()
        path = request.url.path

        if any(path.startswith(p) for p in self.WHITELIST_PREFIXES):
            return await call_next(request)

        # Handle canon enforcement for mutations.
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and settings.ENFORCE_CANON_RATIFIED:
            db = request.app.state.current_canon_status
            if db != "RATIFIED":
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": (
                            f"Cannot mutate: current Canon is in state '{db}'. "
                            "Mutations require a RATIFIED Canon (governance gate)."
                        ),
                        "current_canon_status": db,
                        "request_id": request_id,
                    },
                )

        response = await call_next(request)

        # Audit log.
        duration_ms = (time.time() - start) * 1000
        logger.info(
            "request_id=%s method=%s path=%s status=%d duration_ms=%.1f",
            request_id,
            request.method,
            path,
            response.status_code,
            duration_ms,
        )

        return response
