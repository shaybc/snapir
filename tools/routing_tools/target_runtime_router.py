TARGET_AGENT_BY_LANGUAGE = {
    "java": "JavaServiceGenerationAgent",
    "nodejs": "NodejsServiceGenerationAgent",
    "python": "PythonServiceGenerationAgent",
}


def route_to_target_agents(
    target_languages: list[str],
    operation_id: str,
    channel: str,
) -> list[str]:
    return [TARGET_AGENT_BY_LANGUAGE[language] for language in target_languages]
