from pathlib import Path

from google.adk.agents import LlmAgent

from .response.file_entry import FileEntry
from .response.file_list import FileList


TARGET_DIR = Path(r"c:\\temp")


def get_file_list() -> FileList:
    """List files in c:\\temp and return a structured response."""
    if not TARGET_DIR.exists() or not TARGET_DIR.is_dir():
        return FileList(files=[])

    files: list[FileEntry] = []
    for item in sorted(TARGET_DIR.iterdir(), key=lambda p: p.name.lower()):
        if item.is_file():
            files.append(FileEntry(name=item.name, path=str(item.parent)))

    return FileList(files=files)


structured_response = LlmAgent(
    name="structured_response",
    model="gemini-2.5-flash",
    description="Returns structured JSON file listings from c:\\temp.",
    instruction=(
        "You are a strict JSON formatter. Always call the get_file_list tool first "
        "to fetch the file list from c:\\temp, then return exactly one JSON object "
        "that conforms to the output schema. The only valid top-level key is 'files', "
        "and its value is an array of objects with exactly two string fields: "
        "'name' and 'path'. Do not add any other keys, markdown, code fences, "
        "explanations, or text before/after the JSON. If there are no files, return "
        '{"files": []}. Example valid response: '
        '{"files":[{"name":"file1.txt","path":"/docs"}]}'
    ),
    tools=[get_file_list],
    output_schema=FileList,
    output_key="structured_response",
)


root_agent = structured_response
