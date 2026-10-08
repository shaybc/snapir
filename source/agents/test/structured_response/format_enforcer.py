from dotenv import load_dotenv
import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from .models.file_list import FileList

load_dotenv()


format_enforcer_agent = LlmAgent(
    name="format_enforcer",
    model=LiteLlm(
        model=os.getenv("API_MODEL"),
        api_base=os.getenv("API_BASE_URL"),
        api_key=os.getenv("API_KEY")
    ),
    description="Transforms the raw flat file list from session state into structured JSON matching the FileList schema.",
    instruction="""
        You are a formatting agent.

        You will receive a raw list of file strings from {raw_files}.
        Each entry is in the format: "filename - /full/path/to/filename"

        Parse each entry and split it into:
        - "name": the filename (left of " - ")
        - "path": the directory containing the file (the parent of the full path, i.e. strip the filename from the right)

        Return valid JSON matching exactly this structure:

        {
            "files": [
                {
                    "name": "file1.txt",
                    "path": "/docs"
                }
            ]
        }

        If there are no files, return:

        {
            "files": []
        }

        Do not add any other keys, markdown, code fences, explanations,
        or any text before or after the JSON.
    """,
    output_schema=FileList,
    output_key="structured_response",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
