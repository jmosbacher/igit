from typing import ClassVar

from pydantic import BaseModel


class ObjectPacket(BaseModel):
    otype: str
    content: str
