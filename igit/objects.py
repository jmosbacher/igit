
from dataclasses import dataclass
from intervaltree import IntervalTree, Interval


@dataclass
class Object:
    otype: str
    size: int
    content: bytes
        
class Tree(IntervalTree):
    pass

class Blob(Interval):
    pass
