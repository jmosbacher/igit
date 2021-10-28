import re
from copy import copy
import numpy as np
import sys
from abc import ABC, abstractmethod, abstractclassmethod, abstractstaticmethod
from collections.abc import Mapping, MutableMapping, Iterable
from collections import UserDict, defaultdict
from pydoc import locate
import fsspec

from igit.tokenize import tokenize, normalize_token
from ..models import ObjectRef #, BlobRef, TreeRef, Commit, Tag
from ..utils import dict_to_treelib, equal, class_fullname
from ..diffs import Edit, Patch
from ..constants import TREECLASS_KEY



def camel_to_snake(name):
  name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
  return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


class KeyTypeError(TypeError):
    pass

class BaseTree(MutableMapping):
    TREE_CLASSES = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.TREE_CLASSES.append(cls)

        method_name = "new_"+camel_to_snake(cls.__name__)
        def method(self, name,*args, **kwargs):
            self.add_tree(name, cls(*args, **kwargs))
            return self[name]

        method.__name__ = method_name
        setattr(BaseTree, method_name, method)
    
    @classmethod
    def instance_from_dict(cls, d):
        if not isinstance(d, Mapping):
            raise TypeError(f"{d} is not a Mapping")
        if TREECLASS_KEY not in d:
            raise ValueError('Mapping is not a valid tree representation.')
        cls = locate(d[TREECLASS_KEY])
        return cls.from_dict(d)
     
    def add_tree(self, name, tree):
        if name in self:
            raise KeyError(f"A value with the key {name} alread exists.")
        self[name] = tree

    def to_nested_dict(self, sort=False):
        items = self.to_dict().items()
        if sort:
            items = sorted(items)
        d = {}
        for k,v in items:
            if isinstance(v, BaseTree):
                d[k] = v.to_nested_dict(sort=sort)
            else:
                d[k] = v
        return d

    def to_nested_label_dict(self)->dict:
        d = self.to_label_dict()
        for k,v in d.items():
            if isinstance(v, BaseTree):
                d[k] = v.to_nested_label_dict()
        return d

    def to_paths_dict(self, sep='/')->dict:
        d = self.to_label_dict()
        paths = {}
        for k,v in d.items():
            if isinstance(v, BaseTree):
                for k2,v2 in v.to_paths_dict().items():
                    paths[k+sep+k2] = v2
            else:
                paths[k] = v
        paths[TREECLASS_KEY] = class_fullname(self)
        return paths
    
    def sync(self, m: MutableMapping, sep='/'):
        
        if hasattr(m, 'fs'):
            sep = m.fs.sep
        paths = self.to_paths_dict(sep=sep)
        for k in m.keys():
            if k not in paths:
                del m[k]
        for k,v in paths.items():
            m[k] = v
        return m

    def persist(self, path, serializer="msgpack-dill"):
        from igit.storage import ObjectStorage

        m = fsspec.get_mapper(path)
        store = ObjectStorage(m, serializer=serializer,)
        return self.sync(store)

    @classmethod    
    def from_paths_dict(cls, d, sep='/'):
        if TREECLASS_KEY in d:
            cls = locate(d[TREECLASS_KEY])
        tree = defaultdict(dict)
        for k in d.keys():
            if k.startswith('.'):
                continue
            label,_, rest = k.partition(sep)
            if rest:
                tree[label][rest] = d[k]
            else:
                tree[k] = d[k]
        tree = dict(tree)
        new_tree = {}
        for k,v in tree.items():
            if k.startswith('.'):
                continue
            if isinstance(v, dict) and TREECLASS_KEY in v:
                new_tree[k] = BaseTree.from_paths_dict(v, sep=sep)
            else:
                new_tree[k] = v
        return cls.from_label_dict(new_tree)

    def to_echarts_series(self, name)->dict:
        d = self.to_label_dict()
        children = []
        for k,v in d.items():
            if isinstance(v, BaseTree):
                child = v.to_echarts_series(k)
            else:
                child = {"name": k, "value": str(v)}
            children.append(child)
        return {"name": name, "children": children }

    def echarts_tree(self, label="Tree view"):
        from ..visualizations import echarts_graph
        import panel as pn
        pn.extension('echarts')
        echart = echarts_graph(self.to_echarts_series("root"), label)
        echart_pane = pn.pane.ECharts(echart, width=700, height=400, sizing_mode="stretch_both")
        return echart_pane

    def to_treelib(self, **kwargs):
        d = self.to_nested_dict()
        return dict_to_treelib(d, **kwargs)

    def __repr__(self):
        label = camel_to_snake(self.__class__.__name__)
        return self.to_treelib(parent=label).show(stdout=False)

    def _ipython_key_completions_(self):
        return list(self.keys())

    __str__ = __repr__

    def hash_object(self, store, obj, otype="blob"):
        if isinstance(obj, BaseTree):
            obj = obj.to_merkle_tree(store)
            otype = "tree"
        return self._hash_object(store, obj, otype)

    def to_merkle_tree(self, store):
        tree = self.__class__()
        for k,v in sorted(self.items()):
            if isinstance(v, BaseTree):
                v = v.to_merkle_tree(store)
            tree[k] = store.hash_object(v)
        return tree

    def hash_tree(self, store):
        return self.hash_object(store, self)

    def deref(self, store, recursive=True):
        d = {}
        for k,v in self.items():
            if recursive and hasattr(v, "deref"):
                v = v.deref(store, recursive=recursive)
            d[k] = v
        return self.__class__.from_dict(d)

    def _hash_object(self, store, obj, otype):
        return store.hash_object(obj)
      
    def iter_subtrees(self):
        for k,v in self.items():
            if isinstance(v, BaseTree):
                yield k,v
            elif isinstance(v, ObjectRef) and v.otype=="tree":
                yield k,v
    
    @property
    def sub_trees(self):
        return {k:v for k,v in self.iter_subtrees()}

    def __containes__(self, key):
        return key in list(self.keys())

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return tokenize(self) == tokenize(other)
        if not sorted(self.keys()) == sorted(other.keys()):
            return False
        for k,v in self.items():
            if not equal(v, other[k]):
                return False
        return True
    
    def _igit_hash_object_(self, odb):
        return self.hash_tree(odb)

    @abstractstaticmethod
    def compatible_keys(keys: Iterable)->bool:
        pass

    @abstractclassmethod
    def from_dict(cls, d: Mapping):
        pass
    
    @abstractmethod
    def to_dict(self)->dict:
        pass

    @abstractclassmethod
    def from_label_dict(cls, d):
        pass
    
    @abstractmethod
    def to_label_dict(self)->dict:
        pass

    @abstractmethod
    def to_native(self):
        pass
    
    @abstractmethod 
    def diff(self, other):
        pass

    @abstractmethod 
    def filter_keys(self, pattern):
        pass

    def diff_edits(self, other):
        diff = self.diff(other)
        return get_edits(diff)

    def apply_diff(self, diff):
        result = self.__class__.from_dict(self.to_dict())
        for k,v in diff.items():
            if isinstance(v, Patch):
                v.apply(k, result)
            elif isinstance(v, BaseTree):
                result[k] = result[k].apply_diff(v)
        return result

def get_edits(diff):
    edits = diff.__class__()
    for k,v in diff.items():
        if isinstance(v, BaseTree):
            cs = get_edits(v)
            if len(cs):
                edits[k] = cs
        elif isinstance(v, Edit):
            edits[k] = v
    return edits


@normalize_token.register(BaseTree)
def normalize_tree(tree):
    return tuple((k,normalize_token(tree[k])) for k in sorted(tree.keys()))
