import logging
import litellm

from dotenv import load_dotenv
import os

from google.adk.agents import Agent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

from .file_lister import file_lister_agent
from .format_enforcer import format_enforcer_agent

# load the values from the .env file into the os running environment
load_dotenv()

# activate lite-llm debug and verbose mode
logging.basicConfig(level=logging.DEBUG)
litellm._turn_on_debug()
os.environ['LITELLM_LOG'] = 'DEBUG'


# Sequential pipeline: list files -> enforce format
# This sub-pipeline is invoked by the root agent when the user asks about files.
file_listing_pipeline = SequentialAgent(
    name="file_listing_pipeline",
    description="Lists available files and returns them as structured JSON. Call this when the user asks to list or see available files.",
    sub_agents=[file_lister_agent, format_enforcer_agent],
)


root_agent = Agent(
    name="tool_caller_structured",
    model=LiteLlm(
        model=os.getenv("API_MODEL"),
        api_base=os.getenv("API_BASE_URL"),
        api_key=os.getenv("API_KEY")
    ),
    description="A helpful Python code assistant expert in Google ADK.",
    instruction="""
        You are a helpful Python code assistant that is an expert in Google ADK (Agent Development Kit).

        You can answer general questions normally.

        When the user asks to list, see, or get available files, delegate to the
        `file_listing_pipeline` agent. Do not attempt to list files yourself.

        After the pipeline returns, relay the structured result to the user.
    """,
    sub_agents=[file_listing_pipeline],
)
