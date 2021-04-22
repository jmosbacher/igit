from collections.abc import Mapping

from .object_store import ObjectStore
from .refs import Refs, ObjectRef, Commit
from .trees import BaseTree, collect_intervals


class CommitError(RuntimeError):
    pass


class IGit:
    _head: str
    branches: dict
#     config: dict
#     description: str
#     hooks: dict
#     info: str
    encoder: str
    objects: ObjectStore
    refs: Refs
    index: ObjectRef
    working_tree: BaseTree

    def __init__(self, working_tree, head, branches, index, objects, refs, encoder):
        if isinstance(working_tree, Mapping):
            working_tree = BaseTree.instance_from_dict(working_tree)
        if not isinstance(working_tree, BaseTree):
            raise TypeError

        self.working_tree = working_tree
        self._head = head
        self.branches = branches
        self.index = index
        self.objects = objects
        self.refs = refs
        self.encoder = encoder
        
    @classmethod
    def clone(cls, url):
        pass
    
    @property
    def HEAD(self):
        if not len(self.refs.heads):
            return None
        if self._head in self.refs.heads:
            return self.refs.heads[self._head]
        if self._head in self.refs.tags:
            return self.refs.tags[self._head]
        return self.objects.get_object(self._head)

    @property
    def HEAD_TREE_REF(self):
        if self.HEAD is None:
            return None
        return self.objects.get_object(self.HEAD).tree

    @property
    def HEAD_TREE(self):
        if self.HEAD_TREE_REF is None:
            return None
        return self.objects.get_object(self.HEAD_TREE_REF)

    @property
    def INDEX(self):
        return self.index

    @property
    def INDEX_TREE(self):
        if self.index is None:
            index = self.working_tree.__class__()
        else:
            index = self.objects.get_object(self.index, resolve_refs=True)
        return index

    @property
    def detached(self):
        return self._head not in self.refs.heads

    def status(self):
        pass

    def cat_file(self, key):
        return self.objects.get_object(key, resolve_refs=False)

    def add(self, *keys):
        index = self.INDEX_TREE
        if not keys:
            keys = self.working_tree.keys()
        for key in keys:
            index[key] = self.working_tree[key]
        self.index = self.objects.hash_object(index, encoder=self.encoder)

    def commit(self, message, author='', commiter='',):
        if self.has_unstaged_changes:
            raise CommitError("You have unstaged changes in your working tree.")
        commit = Commit(parent=self.HEAD, tree=self.index, comment=message,
                        author=author, commiter=commiter)
        cref = self.objects.hash_object(commit, encoder=self.encoder)
        self.refs.heads[self._head] = cref
        if self.HEAD is None:
            self.branches[self._head] = cref
        return cref
    
    @property
    def has_unstaged_changes(self):
        index = self.INDEX_TREE
        return bool(index.nested_symmetric_difference(self.working_tree))

    def checkout(self, key, branch=False):
        if branch:
            self.branch(key)
        if key in self.refs.heads:
            ref = self.refs.heads[key]
        else:
            ref = key
        commit = self.objects.get_object(ref)
        tree = self.objects.get_object(commit.tree)
        self.working_tree = tree
        self.index = commit.tree
        self._head = key
        return key

    def branch(self, name=None):
        if name is None:
            return self._head
        if name in self.refs.heads:
            raise ValueError("a branch with this name already exists.")
        ref = self.HEAD
        self.refs.heads[name] = ref
        return ref

    def merge(self, onto):
        pass
    
    def fetch(self, remote=None):
        pass
    
    def pull(self, remote=None):
        pass
        
    def push(self, remote=None):
        pass
