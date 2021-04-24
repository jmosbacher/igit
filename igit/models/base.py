from pydantic import BaseModel
from typing import ClassVar

class BaseObject(BaseModel):
    otype: ClassVar = "object"

