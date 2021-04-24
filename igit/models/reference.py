from typing import ClassVar
from .base import BaseObject
from pydantic import BaseModel, Field
from typing import Mapping, ClassVar

from ..serializers import SERIALIZERS, DEFAULT_SERIALIZER

class SymbolicRef(BaseModel):
    pass

class Reference(BaseModel):
    pass

class ObjectRef(Reference):
    key: str
    otype: ClassVar
    size: int = -1
    serializer: str

    @staticmethod
    def _deref(key, store, serializer):
        serializer = SERIALIZERS[serializer]
        data = store.get(key)
        obj = serializer.cat_object(data, verify=key)
        return obj

    def deref(self, store):
        obj = self._deref(self.key, store, self.serializer)
        if hasattr(obj, "deref"):
            obj = obj.deref(store)
        return obj

class BlobRef(ObjectRef):
    otype: ClassVar = "blob"

class TreeRef(ObjectRef):
    otype: ClassVar = "tree" 
    tree_class: str

class CommitRef(ObjectRef):
    otype: ClassVar = "commit"

    def deref_tree(self, store):
        commit = self.deref(store)
        return commit.tree.deref(store)

    def deref_parent(self, store):
        commit = self.deref(store)
        return commit.parent.deref(store)

class Tag(CommitRef):
    otype: ClassVar = "tag"
    tagger: str
    tag: str

class Branch(CommitRef):
    name: str

class MergeCommitRef(CommitRef):
    otype: ClassVar = "merge"

    def deref_parents(self, store):
        commit = self.deref(store)
        return [ref.deref(store) for ref in commit.parents]

class RefLog:
    pass

class HEAD(SymbolicRef):
    pass

class Commit(Reference):
    otype: ClassVar = "commit"

    tree: TreeRef
    parent: CommitRef = None
    author: str = None
    commiter: str = None
    message: str

    @property
    def is_root(self):
        return self.parent is None

class AnnotatedTag(Commit):
    otype: ClassVar = "atag"
    tagger: str
    tag: str

class MergeCommit(Commit):
    otype: ClassVar = "merge"
    parents: list
