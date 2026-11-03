"""A configured format subtree with a reusable public component contract."""
from pydantic import model_validator
from models.native_component_bundle import NativeComponentBundle
from models.format_metadata_compatibility import discard_internal_chain_metadata


class NativeFormatSubtreeBundle(NativeComponentBundle):
    """Read old artifacts while omitting internal-call descriptions from new contracts."""
    _read_historical_chain_metadata = model_validator(mode='before')(discard_internal_chain_metadata)
