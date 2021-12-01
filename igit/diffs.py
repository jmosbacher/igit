from collections.abc import Iterable, Mapping
from tokenize import tokenize
from typing import Any

import numpy as np
from pydantic import BaseModel

from .models import Commit
# from .trees import BaseTree
from .utils import Dispatch, equal

diff_object = Dispatch()


def diff_dict(old, new):
    inserted = {k: v for k, v in new.items() if k not in old}
    deleted = {k: v for k, v in old.items() if k not in new}
    changed = {}


class Patch(BaseModel):
    new: Any

    def apply(self, key, tree):
        tree[key] = self.new


class Edit(Patch):
    old: Any


class Insertion(Patch):
    old: Any = None


class Deletion(Patch):
    new: Any = None

    def apply(self, tree):
        del tree[self.key]


class Diff(BaseModel):
    old: str
    new: str
    diffs: dict

    def apply(self, tree):
        for k, v in self.diffs.items():
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


class Hunk(BaseModel):
    pass


class IntHunk(Hunk):
    diff: int


class FloatHunk(Hunk):
    diff: float


class DictHunk(Hunk):
    inserted: dict
    removed: list
    replaced: dict


class ListHunk(Hunk):
    inserted: list
    removed: list


# class ArrayHunk(Hunk):
#     diff: np.ndarray

# class ObjectHunk(Hunk):
#     old: object
#     new: object


def has_diffs(store, t1, t2):
    t1 = t1.to_merkle_tree(store)
    t2 = t2.to_merkle_tree(store)
    return not t1 == t2
    # for k,v in t1.items():
    #     if k not in t2:
    #         return True
    #     if not equal(v, t2[k]):
    #         return True
    # for k,v in t2.items():
    #     if k not in t1:
    #         return True
    # return False


def first_diff(t1, t2):
    for k, v in t1.items():
        if k not in t2:
            return k, None
        if not equal(v, t2[k]):
            return v, t2[k]
    for k, v in t2.items():
        if k not in t1:
            return None, k


def diff(l, r, equal):
    from igit.trees import BaseTree
    if not isinstance(l, type(r)):
        return Edit(old=l, new=r)
    if isinstance(l, BaseTree):
        return l.diff(r)
    if isinstance(l, list):
        if len(l) != len(r):
            return Edit(old=l, new=r)
        return [diff(ll, rr, equal) for ll, rr in zip(l, r)]
    if isinstance(l, dict):
        if len(l) != len(r):
            return Edit(old=l, new=r)
        return {k: diff(l[k], r[k]) for k in l}
    if hasattr(l, "_igit_diff_"):
        return l._igit_diff_(r)
    if not equal(l, r):
        return Edit(old=l, new=r)
