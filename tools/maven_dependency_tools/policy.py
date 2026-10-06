"""Approve dependency proposals without permitting legacy Composer runtime jars."""


def validate_dependency_policy(dependency, allowed_ibm_artifacts=()) -> None:
    """Reject legacy runtime artifacts; IBM client exceptions require exact coordinates."""
    identity = f"{dependency.group_id}:{dependency.artifact_id}".lower()
    if any(token in identity for token in ("wsbcc", "websphere", "composer-runtime", "com.ibm.dse")):
        raise ValueError("Legacy Composer runtime dependencies are prohibited")
    if dependency.group_id.lower().startswith("com.ibm") and dependency.coordinates not in allowed_ibm_artifacts:
        raise ValueError("IBM client dependency requires explicit artifact/version approval")
