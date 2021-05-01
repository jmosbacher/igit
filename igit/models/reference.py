from typing import ClassVar, List
from .base import BaseObject
from pydantic import BaseModel, Field
from typing import Mapping, ClassVar

from ..utils import hierarchy_pos, min_ch


class SymbolicRef(BaseObject):
    pass

class Reference(BaseObject):
    pass
        
class ObjectRef(Reference):
    key: str
    otype: ClassVar
    size: int = -1

    def __eq__(self, other):
        if isinstance(other, Reference):
            return self.key == other.key
        if isinstance(other, str):
            return self.key == other
        return False
    
    @staticmethod
    def _deref(key, store):
        obj = store.get(key)
        return obj

    def deref(self, store, recursive=True):
        obj = self._deref(self.key, store)
        if recursive and hasattr(obj, "deref"):
            obj = obj.deref(store, recursive)
        return obj
    
    def __str__(self):
        return self.key

    def __hash__(self):
        return hash(self.key)

class BlobRef(ObjectRef):
    otype: ClassVar = "blob"

class TreeRef(ObjectRef):
    otype: ClassVar = "tree"
    tree_class: str = "BaseTree"

class CommitRef(ObjectRef):
    otype: ClassVar = "commit"

    def deref_tree(self, store):
        commit = self.deref(store)
        return commit.tree.deref(store)

    def deref_parent(self, store):
        commit = self.deref(store)
        return commit.parent.deref(store)

    def _to_digraph(self, db, dg, max_char=40):
        commit = self.deref(db)
        dg.add_node(self.key[:max_char], is_root=commit.is_root, **commit.dict())
        if commit.is_root:
            return
        parent = commit.parent
        dg.add_edge(self.key[:max_char], parent.key[:max_char])
        parent._to_digraph(db, dg, max_char=max_char)

    def digraph(self, db, max_char=None):
        if max_char is None:
            max_char = min_ch(db)
        import networkx as nx
        dg = nx.DiGraph()
        self._to_digraph(db, dg, max_char)
        return dg

    def visualize_heritage(self, db):
        import panel as pn
        import holoviews as hv
        
        pn.extension()
        # hv.extension("bokeh")
        dg = self.digraph(db)
        layout ={k: [v[1], v[0]] for k,v in hierarchy_pos(dg, vert_gap=1).items()}
        graph = hv.Graph.from_networkx(dg, layout)
        graph = graph.opts(node_alpha=0.2, node_hover_fill_color="red", xaxis=None, yaxis=None, toolbar=None,
                        node_hover_alpha=1, node_size=20, invert_xaxis=False, 
                        tools=['hover'], directed=True, arrowhead_length=0.01, )
        return pn.panel(graph, sizing_mode="stretch_both")

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

    def __hash__(self):
        return hash((self.otype, self.tree.key, self.parent.key,
                 self.author, self.commiter, self.message))

    @property
    def is_root(self):
        return self.parent is None


class AnnotatedTag(Commit):
    otype: ClassVar = "atag"
    tagger: str
    tag: str

   
class MergeCommit(Commit):
    otype: ClassVar = "merge"
    parents: List[CommitRef]

    def __hash__(self):
        return hash((self.otype, self.tree.key, tuple(p.key for p in self.parents),
                 self.author, self.commiter, self.message))

