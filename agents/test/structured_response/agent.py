from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent
from pydantic import BaseModel


TARGET_DIR = Path(r"c:\\temp")


class FileEntry(BaseModel):
    name: str
    path: str


class StructuredResponseOutput(BaseModel):
    files: list[FileEntry]


def get_file_list() -> StructuredResponseOutput:
    """List files in c:\\temp and return a structured response."""
    if not TARGET_DIR.exists() or not TARGET_DIR.is_dir():
        return StructuredResponseOutput(files=[])

    files: list[FileEntry] = []
    for item in sorted(TARGET_DIR.iterdir(), key=lambda p: p.name.lower()):
        if item.is_file():
            files.append(FileEntry(name=item.name, path=str(item.parent)))

    return StructuredResponseOutput(files=files)


structured_response = LlmAgent(
    name="structured_response",
    model="gemini-2.5-flash",
    description="Returns structured JSON file listings from c:\\temp.",
    instruction=(
        "Use the get_file_list tool to retrieve file names from c:\\temp and "
        "respond with JSON only in this exact schema: "
        '{"files":[{"name":"<filename>","path":"<parent_path>"}]}'
    ),
    tools=[get_file_list],
    output_schema=StructuredResponseOutput,
    output_key="structured_response",
)


root_agent = structured_response
