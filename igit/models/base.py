from pydantic import BaseModel
from typing import ClassVar

class BaseObject(BaseModel):
    otype: ClassVar = "object"
    
    def __hash__(self):
        return hash(self.json())
