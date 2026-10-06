"""Invoke ADK with explicit inputs and collect the final text response."""

import asyncio
import os

from models.pipeline_configuration import PipelineConfiguration


class AdkExecutor:
    """Run a bounded model request; credentials remain in the process environment."""

    def __init__(self, profile: PipelineConfiguration):
        self.profile = profile

    def execute(self, instruction: str, payload: str) -> str:
        """Return final model text, with a timeout and bounded transport retries."""
        error = None
        for _ in range(self.profile.max_model_attempts):
            try:
                return asyncio.run(asyncio.wait_for(
                    self._execute(instruction, payload), self.profile.model_timeout_seconds
                ))
            except (ImportError, ValueError):
                raise
            except Exception as exc:
                error = exc
        raise RuntimeError("Model execution failed after configured attempts") from error

    async def _execute(self, instruction: str, payload: str) -> str:
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        if self.profile.model_provider == "litellm":
            try:
                from google.adk.models.lite_llm import LiteLlm
            except ImportError as exc:
                raise ValueError("Compatible endpoints require google-adk[extensions]") from exc
            key = os.environ.get(self.profile.model_api_key_environment)
            if not key:
                raise ValueError("Configured model credential environment variable is missing")
            model = LiteLlm(model=self.profile.model_name, api_base=self.profile.model_base_url, api_key=key)
        else:
            model = self.profile.model_name.removeprefix("gemini/")
        agent = LlmAgent(name="MigrationRuntime", model=model, instruction=instruction, tools=[])
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="snapir_runtime", user_id="migration")
        runner = Runner(app_name="snapir_runtime", agent=agent, session_service=sessions)
        async for event in runner.run_async(
            user_id="migration", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=payload)]),
        ):
            if event.is_final_response() and event.content:
                text = "".join(part.text or "" for part in event.content.parts or [])
                if text.strip():
                    return text
        raise RuntimeError("Model returned no final text")
