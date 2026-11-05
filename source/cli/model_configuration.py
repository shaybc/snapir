"""Collect model connection settings for new migration profiles."""


def collect_model_configuration(prompt_text):
    """Prompt with LiteLLM defaults, storing the credential variable name only."""
    provider = prompt_text("model_provider (gemini, litellm, or mock)", "litellm")
    while provider not in {"gemini", "litellm", "mock"}:
        print("Choose gemini, litellm, or mock")
        provider = prompt_text("model_provider (gemini, litellm, or mock)", "litellm")
    return dict(
        model_provider=provider,
        model_name=prompt_text("model_name", "openai/your-model-name"),
        model_base_url=prompt_text("model_base_url", "https://your-endpoint.example/v1"),
        model_api_key_environment=prompt_text(
            "model_api_key_environment (environment variable name, not the API key)",
            "SNAPIR_LLM_API_KEY",
        ),
    )
