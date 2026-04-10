from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness payload for load balancers and orchestrators."""

    status: str = Field(examples=["ok"])
