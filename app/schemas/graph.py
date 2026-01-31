from typing import Annotated
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# ==================================================
# LangGraph State Schema
# ==================================================
class GraphState(BaseModel):
    """
    The central state object passed between graph nodes.
    """
    
    # 'add_messages' is a reducer. It tells LangGraph:
    # "When a new message comes in, append it to the list rather than overwriting it."
    messages: Annotated[list, add_messages] = Field(
        default_factory=list, 
        description="The conversation history"
    )
    
    # Context retrieved from Long-Term Memory (mem0ai)
    long_term_memory: str = Field(
        default="", 
        description="Relevant context extracted from vector store"
    )