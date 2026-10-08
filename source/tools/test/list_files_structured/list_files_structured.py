from pathlib import Path
from dotenv import load_dotenv
import os

# load the values from the .env file into the os running environment
load_dotenv()

ROOT_DIR = Path(os.getenv("ALLOWED_DIR"))


def list_files_structured() -> list[str]:
    """
    Get the current available files that can be accessed and read, as a flat
    list of strings in the format: ["name - /full/path/to/name", ...]

    This simplified format is intentionally different from the structured
    FileList/FileEntry schema — the format_enforcer agent is responsible
    for transforming this into the correct structured output.
    """

    if not ROOT_DIR.exists() or not ROOT_DIR.is_dir():
        return []

    return [
        f"{item.name} - {str(item)}"
        for item in sorted(ROOT_DIR.iterdir(), key=lambda p: p.name.lower())
        if item.is_file()
    ]
