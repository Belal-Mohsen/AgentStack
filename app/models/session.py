from typing import TYPE_CHECKING, List
from sqlmodel import Field, Relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User

# ==================================================
# Session Model
# ==================================================
class Session(BaseModel, table=True):
    """
    Represents a specific chat conversation/thread.
    This links the AI's memory to a specific context.
    """
    
    # We use String IDs (UUIDs) for sessions to make them hard to guess
    id: str = Field(primary_key=True)
    
    # Foreign Key: Links this session to a specific user
    user_id: int = Field(foreign_key="user.id")
    
    # Optional friendly name for the chat (e.g., "Recipe Ideas")
    name: str = Field(default="")
    
    # Relationship link back to the User
    user: "User" = Relationship(back_populates="sessions")