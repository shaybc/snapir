from pydantic import BaseModel

from .file_entry import FileEntry


class FileList(BaseModel):
    files: list[FileEntry]
