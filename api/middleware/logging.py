import structlog
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

# Configure structlog to output JSON with the required fields
def configure_structlog():
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate a request ID for each request and bind it to structlog context.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        # Bind the request ID to the structlog contextvars for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        # Also add service name (we can get it from the app or hardcode for now)
        structlog.contextvars.bind_contextvars(service="api")
        # Process the request
        response = await call_next(request)
        # Clear the contextvars after the request (optional, but good practice)
        structlog.contextvars.clear_contextvars()
        return response

# We'll also create a function to get a logger with the service name
def get_logger(service_name: str):
    """
    Returns a structlog logger with the service name bound.
    """
    return structlog.get_logger(service=service_name)