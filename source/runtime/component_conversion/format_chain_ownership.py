"""Retain configured occurrence ownership for composition, without describing Java internals."""


def chain_ownership(request):
    """Describe existing child ownership and locally generated occurrence ownership."""
    inherited={item['occurrence_id']:dict(item) for item in request.get('inherited_format_chain_ownership',[])}
    return [inherited.get(chain['occurrence_id'],dict(occurrence_id=chain['occurrence_id'],
        group_id=request['group_id'],type_name=request['native_package']+'.'+chain['class_name']))
        for chain in request.get('format_chains',[])]
