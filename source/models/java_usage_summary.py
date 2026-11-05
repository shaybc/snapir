"""Describe exact global Java reference multiplicity without per-source-site use expansion."""

from pydantic import BaseModel, Field


class JavaUsageSummary(BaseModel):
    """One component contribution from a configured root to an original operation consumer."""

    implementation_id: str
    operation_key: str
    operation_id: str
    channel: str | None = None
    reference_count: int = Field(ge=1)
