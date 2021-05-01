import re
from copy import copy
import numpy as np
import sys
from abc import ABC, abstractmethod, abstractclassmethod, abstractstaticmethod
from collections.abc import Mapping, MutableMapping, Iterable
from collections import UserDict, defaultdict

from ..models import ObjectRef, BlobRef, TreeRef, Commit, Tag
from ..utils import dict_to_treelib
from ..diffs import Change, Insertion, Deletion, Diff
from ..settings import DEFAULT_SERIALIZER


def camel_to_snake(name):
  name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
  return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

class KeyTypeError(TypeError):
    pass

class BaseTree(MutableMapping):
    TREE_CLASSES = []


    @classmethod
    def register_tree_class(cls, class_):
        cls.TREE_CLASSES.append(class_)

        method_name = "new_"+camel_to_snake(class_.__name__)
        def method(self, name,*args, **kwargs):
            self.add_group(name, class_(*args, **kwargs))
            return self[name]

        method.__name__ = method_name
        setattr(cls, method_name, method)
        return class_
    
    @classmethod
    def instance_from_dict(cls, d):
        if not isinstance(d, Mapping):
            raise TypeError(f"{d} is not a Mapping")
        keys = d.keys()
        for class_ in cls.TREE_CLASSES:
            if class_.compatible_keys(keys):
                obj = class_.from_dict(d)
                break
        else:
            raise TypeError(f"No Tree type found that supprts {d}")
        return obj

    def add_group(self, name, group):
        if name in self:
            raise KeyError(f"A value with the key {name} alread exists.")
        self[name] = group

    def to_nested_dict(self):
        d = self.to_dict()
        for k,v in self.items():
            if isinstance(v, BaseTree):
                d[k] = v.to_nested_dict()
        return d

    def to_nested_label_dict(self)->dict:
        d = self.to_label_dict()
        for k,v in d.items():
            if isinstance(v, BaseTree):
                d[k] = v.to_nested_label_dict()
        return d

    def to_echarts_series(self, name)->dict:
        d = self.to_label_dict()
        children = []
        for k,v in d.items():
            if isinstance(v, BaseTree):
                child = v.to_echarts_series(k)
            else:
                child = {"name": k, "value": v}
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

    def diff(self, other):
        #TODO: compare hashes via refs instead of using python eq. 
        diffs = {}
        for k,v in self.items():
            if k in other:
                if isinstance(v, BaseTree):
                    d = v.diff(other[k])
                    if d:
                        diffs[k] = d
                elif isinstance(v, np.ndarray):
                    if np.any(np.not_equal(v, other[k])):
                        diffs[k] = Change(key=k, old=v, new=other[k])
                elif v!=other[k]:
                    diffs[k] = Change(key=k, old=v, new=other[k])
            else:
                diffs[k] = Deletion(key=k, old=v)

        for k,v in other.items():
            if k not in self:
                diffs[k] = Insertion(key=k, new=v)
        return diffs

    def hash_object(self, store, obj, otype="blob"):
        if isinstance(obj, BaseTree):
            obj = obj.to_ref_tree(store)
            otype = "tree"
        return self._hash_object(store, obj, otype)

    def to_ref_tree(self, store):
        d = {}
        for k,v in self.items():
            if isinstance(v, ObjectRef):
                d[k] = v
            else:
                d[k] = self.hash_object(store, v)
        return self.__class__.from_dict(d)

    def hash_tree(self, store):
        return self.hash_object(store, self)

    def deref(self, store, recursive=True):
        d = {}
        for k,v in self.items():
            if recursive and hasattr(v, "deref"):
                v = v.deref(store)
            d[k] = v
        return self.__class__.from_dict(d)

    def _hash_object(self, store, obj, otype):
        key = store.hash_object(obj)
        size = sys.getsizeof(obj)
        if isinstance(obj, BaseTree):
            ref = TreeRef(key=key, tree_class=obj.__class__.__name__,
                 size=size)
        else:
            ref = BlobRef(key=key, size=size)
        return ref

    def iter_subtrees(self):
        for k,v in self.items():
            if isinstance(v, BaseTree):
                yield k,v
            elif isinstance(v, ObjectRef) and v.otype=="tree":
                yield k,v
            
    @property
    def sub_trees(self):
        return {k:v for k,v in self.iter_subtrees()}        


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
    
    # @abstractmethod
    # def symmetric_difference(self, other):
    #     pass
    
