"""Read historical format bundles without reviving retired internal-call descriptions."""


def discard_internal_chain_metadata(value):
    """Ignore only the retired field on read; do not include it in new schemas or writes."""
    if isinstance(value,dict) and 'format_chain_bindings' in value:
        return {key:item for key,item in value.items() if key!='format_chain_bindings'}
    return value
