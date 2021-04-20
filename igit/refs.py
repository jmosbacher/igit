from dataclasses import dataclass, field


@dataclass
class SymbolicRef:
    pass

@dataclass
class ObjectRef(SymbolicRef):
    key: str
    otype: str
    size: int

class Tag(SymbolicRef):
    tree: ObjectRef

@dataclass
class Commit(SymbolicRef):
    tree: ObjectRef
    comment: str
    parents: tuple = None
    author: str = ''
    commiter: str = ''
    
@dataclass
class Refs:
    heads: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)

class HEAD(SymbolicRef):
    pass
