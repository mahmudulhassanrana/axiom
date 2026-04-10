from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    service: str = Field(examples=["axiom-api"])
    version: str = Field(examples=["0.1.0"])
