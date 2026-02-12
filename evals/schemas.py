from pydantic import BaseModel, Field

# ==================================================
# Evaluation Score Schema
# ==================================================
class ScoreSchema(BaseModel):
    """
    Structured output for the LLM Judge.
    We force the model to provide a numerical score AND a reasoning.
    This prevents "black box" grading where we don't know why a trace failed.
    """
    score: float = Field(description="A score between 0.0 and 1.0")
    reasoning: str = Field(description="A concise explanation for the score")