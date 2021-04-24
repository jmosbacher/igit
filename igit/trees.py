import re
from copy import copy
from abc import ABC, abstractmethod, abstractclassmethod, abstractstaticmethod
from collections.abc import Mapping, MutableMapping, Iterable
from collections import UserDict
from intervaltree import IntervalTree, Interval

from .models import ObjectRef, BlobRef, TreeRef, Commit, Tag
from .utils import dict_to_treelib
from .serializers import SERIALIZERS, DEFAULT_SERIALIZER
from .diffs import Change, Insertion, Deletion


def camel_to_snake(name):
  name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
  return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

class KeyTypeError(TypeError):
    pass

class BaseTree(MutableMapping):
    TREE_CLASSES = []
    serializer: str = DEFAULT_SERIALIZER
    
    @classmethod
    def register_tree_class(cls, class_):
        cls.TREE_CLASSES.append(class_)

        method_name = "new_"+camel_to_snake(class_.__name__)
        def method(self, name):
            self[name] = class_()
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

    def to_nested_dict(self):
        d = self.to_dict()
        for k,v in self.items():
            if isinstance(v, BaseTree):
                d[k] = v.to_nested_dict()
        return d

    def to_treelib(self, **kwargs):
        d = self.to_nested_dict()
        return dict_to_treelib(d, **kwargs)

    def __repr__(self):
        return self.to_treelib().show(stdout=False)

    __str__ = __repr__

    def nested_symmetric_difference(self, other):
        d = self.symmetric_difference(other)
        for k,v in self.items():
            if isinstance(v, BaseTree):
                diff = v.nested_symmetric_difference(other[k])
                if diff:
                    d[k] = diff
            elif other[k] != v:
                d[k] = v
        return d

    def diff(self, other):
        diffs = {}
        for k,v in self.items():
            if k in other:
                if isinstance(v, BaseTree):
                    d = v.diff(other[k])
                    if d:
                        diffs[k] = d
                elif v != other[k]:
                    diffs[k] = Change(old=v, new=other[k])
            else:
                diffs[k] = Deletion(old=v)

        for k,v in other.items():
            if k not in self:
                diffs[k] = Insertion(new=v)
        return diffs

    def hash_object(self, store, obj):
        for otype, class_ in OTYPES.items():
            if isinstance(obj, class_):
                break
        else:
            otype = "blob"
        if otype == "tree":
            obj = obj.hash_objects(store)
        return self._hash_object(store, obj, otype)

    def hash_objects(self, store):
        d = {k: self.hash_object(store, v) for k,v in self.items()}
        return self.__class__.from_dict(d)

    def hash_tree(self, store):
        return self.hash_object(store, self)

    def deref(self, store):
        d = {}
        for k,v in self.items():
            if hasattr(v, "deref"):
                v = v.deref(store)
            d[k] = v
        return self.__class__.from_dict(d)

    def _hash_object(self, store, obj, otype):
        serializer = SERIALIZERS[self.serializer]
        key, data = serializer.hash_object(obj)
        size = len(data)
        if key not in store:
            store[key] = data
        if isinstance(obj, BaseTree):
            ref = TreeRef(key=key, tree_class=obj.__class__.__name__,
                 size=size, serializer=self.serializer)
        else:
            ref = BlobRef(key=key, size=size, serializer=self.serializer)
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

    @abstractmethod
    def symmetric_difference(self, other):
        pass
    

@BaseTree.register_tree_class
class LabelGroup(UserDict,BaseTree):

    @staticmethod
    def compatible_keys(keys):
        return all([isinstance(k, str) for k in keys])

    @classmethod
    def from_dict(cls, d):
        return cls(d)

    def to_dict(self):
        return dict(self)
    
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise KeyError(f"attribute {key} not found")
    
    def __dir__(self):
        return super().__dir__() + list(self)

    def __bool__(self):
        return bool(len(self.keys()))

    def __repr__(self):
        return BaseTree.__repr__(self)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__ = d

    def symmetric_difference(self, other):
        """
        Credit to Raymond Hettinger
        """
        if not isinstance(other, LabelGroup):
            raise TypeError(f"other must be of type LabelGroup but is of type {type(other)}")
        c = self.to_dict()
        c.update(other)
        for k in (self.keys() & other.keys()):
            del c[k]
        return LabelGroup.from_dict(c)
    

@BaseTree.register_tree_class
class IntervalGroup(BaseTree):
    _tree: IntervalTree
    
    @staticmethod
    def compatible_keys(keys):
        for key in keys:
            if not isinstance(key, tuple):
                return False
            if not len(key) == 2:
                return False
            if not all([isinstance(x, int) for x in key]):
                return False
        return True 

    @classmethod
    def from_dict(cls, d):
        ivs = [Interval(*k, v) for k,v in d.items()]
        return cls(IntervalTree(ivs))

    @classmethod
    def from_label_dict(cls, d):
        ivs = [Interval(*map(int, k.split("-")), v) for k,v in d.items()]
        return cls(IntervalTree(ivs))

    def to_label_dict(self):
        return {f"{iv.begin}-{iv.end}": iv.data for iv in sorted(self._tree)}
        
    def to_dict(self):
        return {(iv.begin,iv.end): iv.data for iv in sorted(self._tree)}
    
    def __init__(self, tree=None):
        if tree is None:
            tree = IntervalTree()
        if not isinstance(tree, IntervalTree):
            raise TypeError("tree must be an instance of IntervalTree.")
        self._tree = tree

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.value(key)
        elif isinstance(key, tuple) and len(key)==2:
            return self.overlap(*key)
        elif isinstance(key, Iterable):
            return self.values(key)
        elif isinstance(key, slice):
            start = key.start or self.start
            stop = key.stop or self.end
            if key.step is None:
                return self.overlap(key.start, key.stop)
            else:
                return self.values(range(start, stop, key.step))

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
        elif isinstance(key, tuple):
            if len(key)==2:
                start, stop = key
                step = None
            elif len(key)==3:
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
    
    def __delitem__(self, key):
        if isinstance(key, tuple) and len(key)==2:
            self._tree.chop(*key)
        
        if isinstance(key, slice):
            self._tree.chop(key.start, key.end)
        raise TypeError("Must pass a tuple of (begin,end) or slice.")
    
    def keys(self):
        for iv in sorted(self._tree):
            yield iv.begin, iv.end

    def items(self):
        for iv in sorted(self._tree):
            yield (iv.begin,iv.end), iv.data

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(self._tree)

    def __bool__(self):
        return bool(len(self._tree))

    def overlap(self, begin, end):
        hits = sorted(self._tree.overlap(begin, end))
        if len(hits)==1:
            return hits[0].data
        else:
            return [Interval(max(iv.begin, begin), min(iv.end, end), iv.data)
                    for iv in hits]

    def value(self, index):
        hits = sorted(self._tree.at(index))
        if len(hits)==1:
            return hits[0].data
        return hits
        
    def values(self, indices):
        return [self.value(i) for i in indices]

    def set_interval(self, begin, end, value):
        self._tree.chop(begin, end)
        self._tree.addi(begin, end, value)

    def symmetric_difference(self, other):
        if not isinstance(other, IntervalGroup):
            raise TypeError(f"other must be of type IntervalGroup but is of type {type(other)}")
        tree = self._tree.symmetric_difference(other._tree)
        return IntervalGroup(tree)
 

def collect_intervals(tree, parent=(), merge_names=True, join_char="_"):
    ivs = []
    if isinstance(tree, IntervalGroup):
        for (begin,end), data in tree.items():
            if merge_names:
                label = join_char.join(parent)
            else:
                label = parent
            if isinstance(data, BaseTree):
                name = parent+(str((begin, end)),)
                ivs.extend(collect_intervals(data, parent=name, merge_names=merge_names, join_char=join_char))
                data = float('nan')

            interval = {"label": label, "begin":begin,
                        "mid":(begin+end)/2 ,"end":end, "data": data}
            ivs.append(interval)
            
    elif isinstance(tree, LabelGroup):
        for k,v in tree.items():
            name = parent+(k,)
            if isinstance(v, BaseTree):
                ivs.extend(collect_intervals(v, parent=name, merge_names=merge_names, join_char=join_char))
    return ivs

OTYPES = {
    "tree": BaseTree,
    "commit": Commit,
    "tag": Tag,
    }
    