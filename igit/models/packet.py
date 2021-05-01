from pydantic import BaseModel
from typing import ClassVar


class ObjectPacket(BaseModel):
    otype: str
    content: str
