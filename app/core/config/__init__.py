# Config module — re-export so "from app.core.config import settings" gets the instance
from app.core.config.settings import Environment, settings

__all__ = ["Environment", "settings"]
