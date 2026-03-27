import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from observability.audit_logger import build_event, log_run

# API-level audit middleware.
# Responsibilities: measure request latency, capture success/failure at HTTP level, and emit audit log per request
class AuditMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next):

        start_time = time.time()
        status = "success"
        error_message = None

        try:
            response = await call_next(request)
            return response

        except Exception as e:
            status = "failure"
            error_message = str(e)
            raise

        finally:
            latency_ms = int((time.time() - start_time) * 1000)

            event = build_event(
                run_id="api_request",
                status=status,
                latency_ms=latency_ms,
                safety_violation_count=0,  # Not available at API layer
                retrieval_hit_count=0,     # Not available at API layer
                flags={"path": str(request.url.path)},
                error=error_message,
            )

            log_run(event)
