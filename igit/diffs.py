from pydantic import BaseModel
from typing import Any
from collections.abc import Mapping, Iterable

import numpy as np
from .models import Commit
from .trees import BaseTree
from .utils import equal

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


def diff_trees(store, t1, t2):
    t1 = t1.to_ref_tree(store)
    t2 = t2.to_ref_tree(store)
    diffs = {}
    for k,v in t1.items():
        if k not in t2:
            diffs[k] = Deletion(key=k, old=v.deref(store))
            continue

        if not equal(v, t2[k]):
            v1 = v.deref(store)
            v2 = t2[k].deref(store)
            if isinstance(v1, BaseTree) and isinstance(v2, BaseTree):
                diffs[k] = diff_trees(store, v1,v2)
            elif not equal(v1, v2):
                diffs[k] = Change(key=k, old=v1, new=v2)
    for k,v in t2.items():
        if k not in t1:
            diffs[k] = Insertion(key=k, new=v)
    return diffs


def has_diffs(t1, t2):
    for k,v in t1.items():
        if k not in t2:
            return True
        if not equal(v, t2[k]):
            return True
    for k,v in t2.items():
        if k not in t1:
            return True
    return False

def first_diff(t1, t2):
    for k,v in t1.items():
        if k not in t2:
            return k, None
        if not equal(v, t2[k]):
            return v,t2[k]
    for k,v in t2.items():
        if k not in t1:
            return None,k
    