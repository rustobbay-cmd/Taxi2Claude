from .common import router as common_router
from .client import router as client_router
from .driver import router as driver_router
from .admin import router as admin_router

__all__ = ["common_router", "client_router", "driver_router", "admin_router"]
