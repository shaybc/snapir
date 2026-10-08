"""Check local model setup without constructing clients or contacting providers."""

import os
from urllib.parse import urlsplit

from models.pipeline_configuration import PipelineConfiguration


def model_readiness_issues(profile: PipelineConfiguration) -> list[str]:
    """Return actionable setup problems without exposing credential values."""
    if profile.model_provider == "mock":
        return []
    issues = []
    if not profile.model_name.strip().removeprefix("gemini/"):
        issues.append("Set model_name in the configuration (AGENT_MODEL is the constants.py default).")
    endpoint = profile.model_base_url.strip()
    if endpoint or profile.model_provider == "litellm":
        try:
            parsed = urlsplit(endpoint)
            host = parsed.hostname or ""
            valid = parsed.scheme in {"http", "https"} and bool(host) and parsed.port != 0
            placeholder = host in {"example.com", "example.org", "example.net", "your-host", "your-proxy-host", "enterprise-llm-host"} or host.endswith((".example", ".invalid"))
            valid = valid and not placeholder and not any(char.isspace() for char in endpoint)
        except ValueError:
            valid = False
        if not valid:
            issues.append("Set model_base_url to a valid provider endpoint in the configuration (LITELLM_BASE_URL is the constants.py default).")
    variable = profile.model_api_key_environment.strip()
    standard_gemini = profile.model_provider == "gemini" and variable in {"GOOGLE_API_KEY", "GEMINI_API_KEY"}
    # Vertex may use application default credentials; their validity is checked by the SDK.
    vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"true", "1"}
    has_key = bool(os.environ.get(variable, "").strip()) if variable else False
    if standard_gemini:
        has_key = has_key or bool(os.environ.get("GOOGLE_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()) or vertex
    if not has_key:
        names = "GOOGLE_API_KEY or GEMINI_API_KEY" if standard_gemini else (variable or "the configured credential variable")
        issues.append(f"Set the API key VALUE in the process environment variable {names}, not in constants.py or YAML. model_api_key_environment (MODEL_API_KEY_ENVIRONMENT default) stores only the variable NAME.")
    return issues


def require_model_readiness(profile: PipelineConfiguration) -> None:
    """Reject incomplete local setup before constructing a model client."""
    issues = model_readiness_issues(profile)
    if issues:
        raise ValueError("Model setup incomplete: " + " ".join(issues))


def intake_model_warning(profile: PipelineConfiguration) -> str | None:
    """Describe incomplete setup while allowing deterministic intake to continue."""
    issues = model_readiness_issues(profile)
    if issues:
        return "Model setup warning: " + " ".join(issues) + " Intake may continue, but planning is unavailable until model setup is complete."
    return None
