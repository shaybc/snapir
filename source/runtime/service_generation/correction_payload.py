"""Remove exact duplicate stage-six project outputs while preserving correction evidence."""

from copy import deepcopy


def deduplicate_generation_correction(payload):
    """Return a copy replacing only duplicate project metadata with an in-request reference."""
    feedback = payload.get('validation_feedback', {})
    previous = payload.get('previous_generation')
    if not previous or feedback.get('generation_output') != previous:
        return payload
    result = deepcopy(payload)
    result['validation_feedback'].pop('generation_output')
    result['validation_feedback']['generation_output_ref'] = 'previous_generation'
    result['correction_evidence_references'] = (
        'validation_feedback.generation_output_ref refers to the exact full previous_generation '
        'object retained in this same request. Read it there; no source, dependency or diagnostic '
        'has been truncated. Return complete files and dependencies, never references, in your response.')
    return result
