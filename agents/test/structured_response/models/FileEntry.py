from pydantic import BaseModel


class FileEntry(BaseModel):
    name: str
    path: str
