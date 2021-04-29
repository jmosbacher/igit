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


def kv_sets(store, t):
    t = t.to_ref_tree(store)
    k = set(t.keys())
    v = set(t.values())
    return t, k, v

def diff_trees(store, t1, t2):
    t1, k1, v1 = kv_sets(t1)
    t2, k2, v2 = kv_sets(t2)

    rlookup1 = {v:k for k,v in t1.items()}
    rlookup2 = {v:k for k,v in t2.items()}

    keys_added = k2.difference(k1)
    keys_removed = k1.difference(k2)
    vals_added =  v2.difference(v1)
    vals_removed =  v1.difference(v2)



