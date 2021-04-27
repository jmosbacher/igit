import re
from copy import copy
import numpy as np
from abc import ABC, abstractmethod, abstractclassmethod, abstractstaticmethod
from collections.abc import Mapping, MutableMapping, Iterable
from collections import UserDict, defaultdict
from intervaltree import IntervalTree, Interval

from .models import ObjectRef, BlobRef, TreeRef, Commit, Tag
from .utils import dict_to_treelib
from .serializers import SERIALIZERS
from .diffs import Change, Insertion, Deletion, Diff
from .settings import DEFAULT_SERIALIZER
from .interval_utils import interval_dict_to_df

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
        from .visualizations import echarts_graph
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
    

@BaseTree.register_tree_class
class LabelGroup(BaseTree):

    def __init__(self, *args, **kwargs):
        self._mapping = dict(*args, **kwargs)
    
    @staticmethod
    def compatible_keys(keys):
        return all([isinstance(k, str) for k in keys])

    @classmethod
    def from_dict(cls, d):
        return cls(d)

    def to_dict(self):
        return dict(self._mapping)
       
    def from_label_dict(cls, d):
        return cls(d)
    
    def to_label_dict(self)->dict:
        return self.to_dict()

    def keys(self):
        return self._mapping.keys()

    def items(self):
        return self._mapping.items()

    def __getattr__(self, key):
        try:
            return self.__getattribute__(key)
        except:
            return self._mapping.get(key)

    def __getitem__(self, key):
        if key in self._mapping:
            return self._mapping[key]
        raise KeyError(f"attribute {key} not found")

    def __setitem__(self, key, value):
        self._mapping[key] = value
    
    def __delitem__(self, key):
        del self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)
    
    def __len__(self):
        return len(self._mapping)

    def __contains__(self, key):
        return key in self._mapping

    def __dir__(self):
        return list(self._mapping.keys()) + super().__dir__()

    def __bool__(self):
        return bool(len(self._mapping.keys()))

    def __repr__(self):
        return BaseTree.__repr__(self)
        
    def __getstate__(self):
        return sorted(self._mapping.items())

    def __setstate__(self, d):
        self._mapping = dict(d)

    def value_viewer(self, k, v):
        if isinstance(v, (int, float)):
            return pn.indicators.Number(name=k, value=v, font_size="35pt", title_size="15pt",
                     format="{value}", sizing_mode="stretch_both")
        return pn.Column(f"## {k}",  f"{v}")

    def explorer(self, title="tree"):
        import panel as pn
        pn.extension()
        from .visualizations import LabelTreeExplorer
        return LabelTreeExplorer(tree=self, label=title)

    def to_native(self):
        d = {}
        for k,v in self.items():
            if isinstance(v, BaseTree):
                d[k] = v.to_native()
            else:
                d[k] = v
        return d


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
    
    def add_group(self, name, group):
        self[name] = group

    def key_to_label(self, key):
        return f"{key[0]}-{key[1]}"

    def label_to_key(self, label):
        return tuple(apply(int, label.split("-")))

    def to_label_dict(self):
        return {f"{iv.begin}-{iv.end}": iv.data for iv in sorted(self._tree)}
        
    def to_dict(self):
        return {(iv.begin,iv.end): iv.data for iv in sorted(self._tree)}
    
    def __init__(self, tree=None, *args, **kwargs):
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

    def __getstate__(self):
        return tuple(sorted([tuple(iv) for iv in self._tree]))

    def __setstate__(self, d):
        ivs = [Interval(*iv) for iv in d]
        self._tree = IntervalTree(ivs)

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

    def to_df(self, title="tree"):
        import pandas as pd
        ivs = []

        for (begin,end), data in self.items():
            if isinstance(data, BaseTree):
                data = float("nan")
            interval = {"label": f"{begin}-{end}", "begin": begin, "parameter": title,
                            "mid":(begin+end)/2 ,"end": end, "data": data}
            ivs.append(interval)
        return pd.DataFrame(ivs)

    def to_native(self):
        ivs = []
        for (begin,end), data in self.items():
            if isinstance(data, BaseTree):
                iv = Interval(begin,end, data.to_native())
            else:
                iv = Interval(begin,end, data)
            ivs.append(iv)
        return IntervalTree(ivs)

    def explorer(self, title="tree"):
        import panel as pn
        pn.extension()
        from .visualizations import IntervalTreeExplorer
        return IntervalTreeExplorer(tree=self, label=title)

@BaseTree.register_tree_class
class ConfigGroup(LabelGroup):

    def __setitem__(self, key, value):
        if isinstance(value, BaseTree) and not isinstance(value, IntervalGroup):
            raise TypeError("Config subgroups can only be of type IntervalGroup")
        super().__setitem__(key, value)

    @staticmethod
    def mergable(name,ivs,begin,end):
        return [Interval(max(iv.begin, begin), min(iv.end, end), (name, iv.data)) for iv in ivs]
    
    def selection(self, begin, end, *keys):
        if not keys:
            keys = self._mapping.keys()
        merged = []
        for k in keys:
            v = self._mapping[k]
            if isinstance(v, IntervalGroup):
                ivs = v.overlap(begin, end)
            else:
                ivs = [Interval(begin, end, v)]
            merged.extend(self.mergable(k, ivs, begin, end))
        tree = IntervalTree(merged)
        tree.split_overlaps()
        cfg = {k:[] for k in keys}
        for iv in tree:
            cfg[iv.data[0]].append(Interval(iv.begin, iv.end, iv.data[1]))
        cfg = {k: sorted(v) for k,v in cfg.items()}
        return cfg

    def selection_df(self, begin, end, *keys):
        return interval_dict_to_df(self.selection(begin, end, *keys))

    def chunk_interval(self, begin, end, *keys):
        config = defaultdict(dict)
        cfg = self.selection(begin, end, *keys)
        for k, ivs in cfg.items():
            for iv in ivs:
                config[(iv.begin, iv.end,)][k] = iv.data
        return dict(config)

    def show_interval(self, begin, end, *keys,  **kwargs):
        import holoviews as hv
        import panel as pn
        pn.extension()
        df = self.selection_df(begin, end, *keys)
        df["label"] = df.value.apply(lambda x: str(x)[:12])
        opts = dict(color="label", responsive=True, cmap="Category10", title="Chunk intervals",
         height=len(df["parameter"].unique())*30+80, line_width=30, alpha=0.5)
        opts.update(**kwargs)
        segments = hv.Segments(df, ["begin","parameter","end", "parameter"], "label").opts(**opts)
        labels = hv.Labels(df, ["mid", "parameter"], "label")
        vline = hv.Overlay([hv.VLine(x).opts(color="grey", line_width=1) for x in df.end.unique()])
        
        return pn.Column(segments*labels*vline, sizing_mode="stretch_both")

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
                        "mid":(begin+end)/2 ,"end": end, "data": data}
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
    