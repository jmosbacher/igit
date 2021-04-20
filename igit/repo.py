from collections.abc import Iterable

from .objects import IntervalTree, Interval
from .object_store import BaseObjectStore, PickleObjectStore
from .refs import Refs, ObjectRef, Commit

class CommitError(RuntimeError):
    pass

class Repo:
    _head: str
    branches: dict
#     config: dict
#     description: str
#     hooks: dict
#     info: str
    objects: BaseObjectStore
    refs: Refs
    index: ObjectRef
    working_tree: IntervalTree

    def __init__(self, working_tree, head, branches, index, objects, refs):
        self.working_tree = working_tree
        self._head = head
        self.branches = branches
        self.index = index
        self.objects = objects
        self.refs = refs
        
    @classmethod
    def init(cls):
        working_tree = IntervalTree()
        head = "master"
        branches = {}
        index = None
        objects = PickleObjectStore()
        refs = Refs()
        return cls(working_tree=working_tree, head=head, branches=branches,
                    index=index, objects=objects, refs=refs)
    
    @classmethod
    def clone(cls, url):
        pass
    
    @property
    def HEAD(self):
        return self.refs.heads.get(self._head, None)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.value(key)
        elif isinstance(key, Iterable):
            return self.values(key)
        elif isinstance(key, slice):
            start = key.start or self.start
            stop = key.stop or self.end
            if key.step is None:
                return self.cut(key.start, key.stop)
            else:
                return self.values(range(start, stop, key.step))

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
        elif isinstance(key, tuple):
            if len(key)==2:
                start, stop = key
                step = None
            if len(key)==3:
                start, stop, step = key
            else:
                raise ValueError("Setting intervals with tuple must be  \
                            of form (start, end) or (start, end, step)")
        else:
            raise TypeError("Wrong type. Setting intervals can only be done using a \
                            slice or tuple of (start, end) or (start, end, step)")
        if start is None:
            start = self.start
        if stop is None:
            stop = self.end
        if step is None:
            self.set_interval(start, stop, value)
        else:
            indices = list(range(start,stop,step))
            for begin,end,val in zip(indices[:-1], indices[1:], value):
                 self.set_interval(begin, end, val)
            
    def value(self, index):
        hits = sorted(self.working_tree.at(index))
        if hits:
            return hits[0].data

    def values(self, indices):
        return [self.value(i) for i in indices]
    
    def status(self):
        pass

    def cat_file(self, key):
        return self.objects.get_object(key, resolve_refs=False)

    def set_interval(self, begin, end, value):
        self.working_tree.chop(begin, end)
        self.working_tree.addi(begin, end, value)
    
    def add(self, begin=None, end=None):
        if begin is None:
            begin = self.working_tree.begin()
        if end is None:
            end = self.working_tree.end() + 1
        if self.index is None:
            index = IntervalTree()
        else:
            index = self.objects.get_object(self.index.key, resolve_refs=True)
        for iv in self.working_tree.overlap(begin, end):
            b,e = max(begin,iv.begin), min(end,iv.end)
            index.chop(b,e)
            index.addi(b,e, iv.data)
        self.index = self.objects.hash_object(index)

    def commit(self, message, author='', commiter='',):
        if self.has_unstaged_changes:
            raise CommitError("You have unstaged changes in your working tree.")
        tref = self.index
        parent = self.HEAD
        if parent is None:
            parents = None
        else:
            parents = (parent, )
        commit = Commit(parents=parents, tree=tref, comment=message,
                        author=author, commiter=commiter)
        cref = self.objects.hash_object(commit)
        self.refs.heads[self._head] = cref
        return cref
    
    @property
    def has_unstaged_changes(self):
        if self.index is None:
            index = IntervalTree()
        else:
            index = self.objects.get_object(self.index.key, resolve_refs=True)
        return bool(index.symmetric_difference(self.working_tree))

    def checkout(self, key):
        commit = self.objects.get_object(key)
        tree = self.objects.get_object(commit.tree.key)
        self.working_tree = tree
        self.index = commit.tree
        self.refs.heads[self._head] = key

    def branch(self, name):
        pass
    
    def merge(self, onto):
        pass
    
    def fetch(self, remote=None):
        pass
    
    def pull(self, remote=None):
        pass
        
    def push(self, remote=None):
        pass

