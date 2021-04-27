from pydantic import BaseModel
from typing import Any
from .models import Commit


class Change(BaseModel):
    key: Any
    old: Any
    new: Any

    def apply(self, tree):
        tree[self.key] = self.new

class Insertion(Change):
    old: Any = None

class Deletion(Change):
    new: Any = None

    def apply(self, tree):
        del tree[self.key]

class Diff(BaseModel):
    old: str
    new: str
    diffs: dict

    def apply(self, tree):
        for k,v in self.diffs.items():
            if isinstance(v, dict):
                self.apply(tree[k])
            else:
                v.apply(tree)

    def __bool__(self):
        return len(self.diffs)

class CommitDiff(Diff):
    old: Commit
    new: Commit
    diff: Diff
