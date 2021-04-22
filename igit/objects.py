
from dataclasses import dataclass
from intervaltree import IntervalTree, Interval
from pydantic import BaseModel

class ObjectPacket(BaseModel):
    otype: str
    content: str
    encoder: str
        
