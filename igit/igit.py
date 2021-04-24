from collections.abc import Mapping

# from .object_store import ObjectStore
from .models import ObjectRef, Commit
from .refs import Refs
from .trees import BaseTree, collect_intervals
from .serializers import SERIALIZERS, DEFAULT_SERIALIZER


class CommitError(RuntimeError):
    pass

def get_object_ref(key, otype, serializer, size=-1):
    for class_ in ObjectRef.__subclasses__():
        if class_.otype == otype:
            return class_(key=key, serializer=serializer, size=size)
    raise KeyError(otype)

class IGit:
    _head: str
#     config: dict
#     description: str
#     hooks: dict
#     info: str
    serializer: str = DEFAULT_SERIALIZER
    objects: Mapping
    refs: Refs
    index: ObjectRef = None
    working_tree: BaseTree

    def __init__(self, working_tree, head, index, objects, refs, serializer):
        if isinstance(working_tree, Mapping):
            working_tree = BaseTree.instance_from_dict(working_tree)
        if not isinstance(working_tree, BaseTree):
            raise TypeError("Working tree must be an instance of BaseTree")
        self.working_tree = working_tree
        self._head = head
        self.index = index
        self.objects = objects
        self.refs = refs
        self.serializer = serializer
        
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
        return self.cat_object(self._head, otype="commit")

    @property
    def HEAD_TREE(self):
        if self.HEAD_TREE is None:
            return None
        return self.HEAD.deref_tree(self.objects)

    @property
    def INDEX(self):
        return self.index

    @property
    def INDEX_TREE(self):
        if self.index is None:
            index = self.working_tree.__class__()
        else:
            index = self.index.deref(self.objects)
        return index

    @property
    def detached(self):
        return self._head not in self.refs.heads

    def status(self):
        pass

    def cat_object(self, ref, otype="blob",):
        if isinstance(ref, ObjectRef):
            return ref.deref(self.objects)
        if isinstance(ref, str):
            return get_object_ref(ref, otype=otype, serializer=self.serializer).deref(self.objects)
        else:
            raise KeyError(ref)

    def hash_object(self, obj, otype="blob"):
        serializer = SERIALIZERS[self.serializer]
        key, data = serializer.hash_object(obj)
        size = len(data)
        if key not in self.objects:
            self.objects[key] = data
        ref = get_object_ref(key, otype=otype, serializer=self.serializer, size=size)
        return ref

    def update_index(self, *keys):
        pass

    def write_tree(self):
        pass

    def add(self, *keys):
        index = self.INDEX_TREE
        if not keys:
            keys = self.working_tree.keys()
        for key in keys:
            index[key] = self.working_tree[key]
        self.index = index.hash_tree(self.objects)
        return self.index

    def commit(self, message, author='', commiter='',):
        if self.has_unstaged_changes:
            raise CommitError("You have unstaged changes in your working tree.")
        commit = Commit(parent=self.HEAD, tree=self.index, message=message,
                        author=author, commiter=commiter)
        cref = self.hash_object(commit, otype="commit")
        self.refs.heads[self._head] = cref
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
        commit = ref.deref(self.objects)
        tree = commit.tree.deref(self.objects)
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
    
    def fs_check(self):
        pass

    def rev_parse(self, key):
        pass