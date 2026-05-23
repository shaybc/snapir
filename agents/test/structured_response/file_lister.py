from dotenv import load_dotenv
import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from tools.test.list_files_structured.list_files_structured import list_files_structured

load_dotenv()


file_lister_agent = LlmAgent(
    name="file_lister",
    model=LiteLlm(
        model=os.getenv("API_MODEL"),
        api_base=os.getenv("API_BASE_URL"),
        api_key=os.getenv("API_KEY")
    ),
    description="Calls the list_files_structured tool and stores the raw result in session state.",
    instruction="""
        You are a file listing agent.
        Call the `list_files_structured` tool exactly once and do nothing else.
        Do not summarize, explain, or reformat the result.
        The tool result will be automatically saved for the next agent to format.
    """,
    tools=[list_files_structured],
    output_key="raw_files",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
