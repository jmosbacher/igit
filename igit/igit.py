from collections.abc import Mapping

# from .object_store import ObjectStore
from .models import ObjectRef, Commit
from .refs import Refs
from .trees import BaseTree, collect_intervals
from .serializers import SERIALIZERS
from .diffs import Diff
from .config import Config
from .settings import DEFAULT_SERIALIZER


class CommitError(RuntimeError):
    pass

def get_object_ref(key, otype, serializer, size=-1):
    for class_ in ObjectRef.__subclasses__():
        if class_.otype == otype:
            return class_(key=key, serializer=serializer, size=size)
    raise KeyError(otype)

class IGit:
    config: Config
#     description: str
#     hooks: dict
#     info: str
    serializer: str = DEFAULT_SERIALIZER
    objects: Mapping
    refs: Refs
    index: ObjectRef = None
    working_tree: BaseTree

    def __init__(self, working_tree, config, index, objects, refs, serializer):
        if isinstance(working_tree, Mapping):
            working_tree = BaseTree.instance_from_dict(working_tree)
        if not isinstance(working_tree, BaseTree):
            raise TypeError("Working tree must be an instance of BaseTree")
        self.working_tree = working_tree
        self.config = config
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
        if self.config.HEAD in self.refs.heads:
            return self.refs.heads[self.config.HEAD]
        if self.config.HEAD in self.refs.tags:
            return self.refs.tags[self.config.HEAD]
        return self.cat_object(self.config.HEAD, otype="commit")

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
        return self.config.HEAD not in self.refs.heads

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
        for key in index.keys():
            if key not in self.working_tree:
                del self.working_tree[key]
        self.index = index.hash_tree(self.objects)
        return self.index

    def commit(self, message, author=None, commiter=None,):
        if self.has_unstaged_changes:
            raise CommitError("You have unstaged changes in your working tree.")
        if author is None:
            author = self.config.user.username
        if commiter is None:
            commiter = self.config.user.username
        commit = Commit(parent=self.HEAD, tree=self.index, message=message,
                        author=author, commiter=commiter)
        cref = self.hash_object(commit, otype="commit")
        self.refs.heads[self.config.HEAD] = cref
        return cref
    
    @property
    def has_unstaged_changes(self):
        index = self.INDEX_TREE
        return bool(index.diff(self.working_tree))

    def checkout(self, key, branch=False):
        if branch:
            self.branch(key)
        if key in self.refs.heads:
            ref = self.refs.heads[key]
        elif key in self.refs.tags:
            ref = self.refs.tags[key]    
        else:
            ref = key
        commit = ref.deref(self.objects)
        tree = commit.tree.deref(self.objects)
        self.working_tree = tree
        self.index = commit.tree
        self.config.HEAD = key
        return key

    def branch(self, name=None):
        if name is None:
            return self.config.HEAD
        if name in self.refs.heads:
            raise ValueError("a branch with this name already exists.")
        ref = self.HEAD
        self.refs.heads[name] = ref
        return ref

    def tag(self, name, annotated=False):
        pass

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

    def cat_tree(self, ref, otype="blob", serializer=DEFAULT_SERIALIZER):
        if isinstance(ref, str):
            ref = self.get_ref(ref)    
        obj = ref.deref(self.objects)
        if isinstance(obj, Commit):
            obj = obj.tree.deref(self.objects)
        if not isinstance(obj, BaseTree):
            raise ValueError(f"reference {ref} does not point to a tree or commit.")
        return obj

    def diff(self, ref1, ref2, otype="commit", serializer=DEFAULT_SERIALIZER):
        tree1 = self.cat_tree(ref1, otype=otype, serializer=serializer)
        tree2 = self.cat_tree(ref2, otype=otype, serializer=serializer)
        diffs = tree1.diff(tree2)
        return Diff(old=str(ref1), new=str(ref2), diffs=diffs)

    def get_ref(self, key):
        if key in self.objects:
            data = self.objects[key]
        else:
            for k in self.objects.keys():
                if k.startswith(key):
                    key = k
                    data = self.objects[k]
                    break
            else:
                raise KeyError(key)
        obj = SERIALIZERS[self.serializer].cat_object(data, verify=key)
        for class_ in ObjectRef.__subclasses__():
            if class_.otype == obj.otype:
                return class_(key=key, serializer=self.serializer, size=-1)
        else:
            raise KeyError(key)
