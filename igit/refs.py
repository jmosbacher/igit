from dataclasses import dataclass, field
from pydantic import BaseModel


class SymbolicRef(BaseModel):
    pass

class Reference(BaseModel):
    pass

class ObjectRef(Reference):
    key: str
    otype: str
    size: int
    encoder: str

class Tag(Reference):
    tree: ObjectRef

class Commit(Reference):
    tree: ObjectRef
    comment: str
    parent: ObjectRef = None
    author: str = None
    commiter: str = None

    @property
    def is_root(self):
        return self.parent is None

class MergeCommit(Commit):
    parents: list

@dataclass
class Refs:
    heads: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)


class HEAD(SymbolicRef):
    pass
