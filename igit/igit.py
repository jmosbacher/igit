import sys
import time
from datetime import datetime
from collections.abc import Mapping
from collections import Counter

# from .object_store import ObjectStore
from .models import ObjectRef, Commit, Tag, AnnotatedTag, User, CommitRef
from .refs import Refs
from .trees import BaseTree, collect_intervals
from .diffs import Diff, has_diffs
from .config import Config
from .storage import IGitObjectStore
from .utils import roundrobin

class CommitError(RuntimeError):
    pass

class MergeError(CommitError):
    pass


def get_object_ref(key, otype, size=-1):
    """
    get an object reference

    Args:
        key :
        otype :
        size : Defaults to -1

    (Generated by docly)
    """
    for class_ in ObjectRef.__subclasses__():
        if class_.otype == otype:
            return class_(key=key, size=size)
    raise KeyError(otype)

class IGit:
    config: Config
#     description: str
#     hooks: dict
#     info: str
    objects: IGitObjectStore
    refs: Refs
    index: ObjectRef = None
    working_tree: BaseTree

    def __init__(self, working_tree, config, index, objects, refs):
        if isinstance(working_tree, Mapping):
            working_tree = BaseTree.instance_from_dict(working_tree)
        if working_tree is not None and not isinstance(working_tree, BaseTree):
            raise TypeError("Working tree must be an instance of BaseTree")
        self.working_tree = working_tree
        self.config = config
        self.index = index
        self.objects = objects
        self.refs = refs
        
    @classmethod
    def clone(cls, url):
        pass
    
    @property
    def bare(self):
        return self.working_tree is None

    @property
    def WORKING_TREE(self):
        if self.working_tree is None:
            self.working_tree = BaseTree.instance_from_dict({})
        return self.working_tree

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
        if self.HEAD is None:
            return None
        return self.HEAD.deref_tree(self.objects)

    @property
    def INDEX(self):
        return self.index

    @property
    def INDEX_TREE(self):
        if self.index is None:
            index = self.WORKING_TREE.__class__()
        else:
            index = self.INDEX.deref(self.objects)
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
            return get_object_ref(ref, otype=otype).deref(self.objects)
        else:
            raise KeyError(ref)

    def hash_object(self, obj, otype="blob"):
        if isinstance(obj, BaseTree):
            return obj.hash_tree(self.objects)
        if hasattr(obj, "otype"):
            otype = obj.otype
        return self.objects.hash_object(obj)

    def update_index(self, *keys):
        pass

    def write_tree(self):
        pass

    def add(self, *keys):
        index = self.INDEX_TREE
        if not keys:
            keys = self.WORKING_TREE.keys()
        for key in keys:
            obj = self.WORKING_TREE[key]
            if not self.objects.consistent_hash(obj):
                raise ValueError(f"{key} of type {type(obj)} cannot be consistently hashed.")
            index[key] = obj
        for key in index.keys():
            if key not in self.WORKING_TREE:
                del self.WORKING_TREE[key]
        self.index = index.hash_tree(self.objects)
        return self.index

    def rm(self, *keys):
        index = self.INDEX_TREE
        if not keys:
            keys = self.WORKING_TREE.keys()
        for key in keys:
            del index[key]
        self.index = index.hash_tree(self.objects)
        return self.index

    def commit(self, message, author=None, commiter=None,):
        if self.has_unstaged_changes:
            raise CommitError("You have unstaged changes in your working tree.")
        if author is None:
            author = self.config.user
        elif isinstance(author, dict):
            author = User(**author)

        if commiter is None:
            commiter = self.config.user
        elif isinstance(commiter, dict):
            commiter = User(**commiter)
        parents = ()
        if self.HEAD is not None:
            parents = (self.HEAD, )
        commit = Commit(parents=parents, tree=self.index, message=message,
                        author=author, commiter=commiter, timestamp=int(time.time()))
        cref = self.hash_object(commit, otype="commit")
        self.refs.heads[self.config.HEAD] = cref
        return cref
    
    @property
    def has_unstaged_changes(self):
        return self.INDEX_TREE != self.WORKING_TREE

    def checkout(self, key, branch=False):
        if self.has_unstaged_changes:
            raise CommitError("You have unstaged changes in your working tree.")
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

    def tag(self, name, annotated=False, tagger=None, message=""):
        cref = self.HEAD
        if annotated:
            if tagger is None:
                tagger = self.config.user
            atag = AnnotatedTag(key=cref.key, tag=name, tagger=tagger, message=message)
            cref = self.hash_object(atag)
        tag = Tag(key=cref.key)
        self.refs.tags[name] = tag
        return tag

    def merge(self, other, message, commiter=None):
        if self.has_unstaged_changes:
            raise MergeError("You have unstaged changes in your working tree.")
        common = self.find_common_ancestor(self.HEAD, other).deref_tree(self.objects)
        ours = self.get_branch_tree(self.HEAD)

        incoming = self.get_branch_tree(other)

        if len( common.diff(ours).diff_edits(common.diff(incoming)) ):
            raise MergeError(f"Cannot merge with {other}, conflicts exist")
        
        if commiter is None:
            commiter = self.config.user
        elif isinstance(commiter, dict):
            commiter = User(**commiter)

        parents = (self.HEAD, self.get_ref(other))
        merged = self.HEAD_TREE.apply_diff(common.diff(incoming))
        merged_ref = merged.hash_tree(self.objects)

        commit = Commit(parents=parents, tree=merged_ref, message=message,
                         commiter=commiter, timestamp=int(time.time()))
        cref = self.hash_object(commit, otype="commit")
        self.refs.heads[self.config.HEAD] = cref
        return cref
    
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

    def commit_graph(self):
        return self.HEAD.digraph(self.objects)

    def show_commits(self):
        return self.HEAD.visualize_heritage(self.objects)

    def cat_tree(self, ref, otype="blob"):
        if isinstance(ref, str):
            ref = self.get_ref(ref)
        obj = ref.deref(self.objects)
        if isinstance(obj, Commit):
            obj = obj.tree.deref(self.objects)
        if not isinstance(obj, BaseTree):
            raise ValueError(f"reference {ref} does not point to a tree or commit.")
        return obj

    def diff(self, ref1, ref2, otype="commit"):
        tree1 = ref1.deref(self.objects)
        tree2 = ref2.deref(self.objects)
        diffs = tree1.diff(tree2)
        return Diff(old=str(ref1), new=str(ref2), diffs=diffs)

    def get_branch_tree(self, branch):
        if isinstance(branch, CommitRef):
                ref = branch
        elif isinstance(branch, str):
            if branch in self.refs.heads:
                ref = self.refs.heads[branch]
            else:
                ref = self.get_ref(branch)
        return ref.deref_tree(self.objects)

    def get_ref(self, key):
        if isinstance(key, ObjectRef):
            return key
        if key in self.refs.heads:
            return self.refs.heads[key]
        if key in self.refs.tags:
            return self.refs.tags[key]

        obj = self.objects.fuzzy_get(key)
        ref = self.objects.hash_object(obj)
        return ref

    def find_common_ancestor(self, *branches):
        refs = []
        for branch in branches:
            if isinstance(branch, CommitRef):
                ref = branch
            elif isinstance(branch, str):
                if branch in self.refs.heads:
                    ref = self.refs.heads[branch]
                else:
                    ref = self.get_ref(branch)
            refs.append(ref)

        keys = Counter()
        for cref in roundrobin(*[r.walk_parents(self.objects) for r in refs]):
            keys[cref.key] += 1
            if keys[cref.key] == len(refs):
                return cref
    