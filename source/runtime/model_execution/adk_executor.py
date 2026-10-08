"""Invoke ADK with explicit inputs and collect the final text response."""

import asyncio
import logging
import os
from contextlib import aclosing
from time import monotonic

from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.readiness import require_model_readiness
from runtime.model_execution.error_details import sanitize_diagnostic
from runtime.model_execution.progress import before_model, after_model, request_headers, response_headers, wait_with_progress


class AdkExecutor:
    """Run a bounded model request; credentials remain in the process environment."""

    def __init__(self, profile: PipelineConfiguration):
        self.profile = profile
        self.component_label = ""

    def execute(self, instruction: str, payload: str) -> str:
        """Return final model text, with a timeout and bounded transport retries."""
        from runtime.model_execution.component_progress import COMPONENT_LABEL
        token = COMPONENT_LABEL.set(self.component_label)
        logger = logging.getLogger(__name__)
        logger.info("Model interaction started", extra={"model_interaction_boundary": "start"})
        try:
            return self._execute_with_retries(instruction, payload)
        finally:
            logger.info("Model interaction ended", extra={"model_interaction_boundary": "end"})
            COMPONENT_LABEL.reset(token)

    def _execute_with_retries(self, instruction, payload):
        """Run transport retries with the current component diagnostic context."""
        from runtime.model_execution.component_progress import component_suffix
        require_model_readiness(self.profile)
        error = None
        logger = logging.getLogger(__name__)
        for attempt in range(1, self.profile.max_model_attempts + 1):
            started = monotonic()
            logger.info("Model execution attempt %s/%s using %s (%s).%s", attempt,
                        self.profile.max_model_attempts, self.profile.model_name, self.profile.model_provider, component_suffix())
            try:
                response = asyncio.run(wait_with_progress(
                    self._execute(instruction, payload), self.profile.model_timeout_seconds
                ))
                logger.info("Model execution completed in %.1f seconds (%s response characters).%s",
                            monotonic() - started, len(response), component_suffix())
                return response
            except (ImportError, ValueError):
                raise
            except Exception as exc:
                error = exc
                logger.warning("Model attempt %s/%s failed after %.1f seconds: %s%s", attempt,
                               self.profile.max_model_attempts, monotonic() - started,
                               sanitize_diagnostic(str(exc)), component_suffix())
        cause = sanitize_diagnostic(str(error)).strip() or type(error).__name__
        cause = " ".join(cause.split())
        logging.getLogger(__name__).error("Model execution failed after %s attempts: %s%s",
                                         self.profile.max_model_attempts, cause, component_suffix(),
                                         exc_info=(type(error), error, error.__traceback__))
        raise RuntimeError(f"Model execution failed after {self.profile.max_model_attempts} attempts: {cause}") from error

    async def _execute(self, instruction: str, payload: str) -> str:
        require_model_readiness(self.profile)
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
            from functools import cached_property
            from google.adk.models import Gemini
            from google.genai import Client

            key = os.environ.get(self.profile.model_api_key_environment)
            if not key and self.profile.model_api_key_environment not in {"GOOGLE_API_KEY", "GEMINI_API_KEY"}:
                raise ValueError("Configured model credential environment variable is missing")
            if key or self.profile.model_provider == "gemini":
                class ConfiguredGemini(Gemini):
                    """Keep the selected process credential in the transient SDK client."""

                    @cached_property
                    def api_client(self):
                        options = types.HttpOptions(async_client_args={"event_hooks": {
                            "request": [request_headers], "response": [response_headers]}})
                        if self.base_url:
                            options.base_url = self.base_url
                        return Client(api_key=key, http_options=options)

                model = ConfiguredGemini(model=self.profile.model_name.removeprefix("gemini/"),
                                         base_url=self.profile.model_base_url or None)
            else:
                model = Gemini(model=self.profile.model_name.removeprefix("gemini/"),
                               base_url=self.profile.model_base_url or None)
        # Instructions are already expanded; a provider prevents ADK state interpolation.
        def literal_instruction(context):
            return instruction

        agent = LlmAgent(name="MigrationRuntime", model=model, instruction=literal_instruction, tools=[],
                         before_model_callback=before_model, after_model_callback=after_model)
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="snapir_runtime", user_id="migration")
        runner = Runner(app_name="snapir_runtime", agent=agent, session_service=sessions)
        final_text = None
        async with aclosing(runner.run_async(
            user_id="migration", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=payload)]),
        )) as events:
            async for event in events:
                if event.is_final_response() and event.content:
                    text = "".join(part.text or "" for part in event.content.parts or [])
                    if text.strip() and final_text is None:
                        final_text = text
        if final_text is not None:
            return final_text
        raise RuntimeError("Model returned no final text")
