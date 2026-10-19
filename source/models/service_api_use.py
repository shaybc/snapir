"""One conversion run's pinned use of a published service API."""

from pydantic import BaseModel, ConfigDict, Field

from models.converted_service_contract import ConvertedServiceContract
from models.service_address import ServiceAddress


class ServiceApiUse(BaseModel):
    """Store the exact contract and selected address inside the run database."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    run_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    contract: ConvertedServiceContract
    address: ServiceAddress
