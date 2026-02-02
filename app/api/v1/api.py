from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.core.config.logging import get_logger
logger = get_logger(__name__)

# ==================================================
# API Router Aggregator
# ==================================================
api_router = APIRouter()

# Include sub-routers with prefixes
# e.g. /api/v1/auth/login
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# e.g. /api/v1/chatbot/chat
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
@api_router.get("/health")
async def health_check():
    """
    Simple liveness probe for load balancers.
    """
    return {"status": "healthy", "version": "1.0.0"}