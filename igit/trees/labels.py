

from .base import BaseTree
from ..utils import equal
from ..diffs import Edit, Insertion, Deletion, Diff


@BaseTree.register_tree_class
class LabelGroup(BaseTree):
    
    def __init__(self, mapping=None, **kwargs):
        if mapping is None:
            mapping = dict(**kwargs)
        self._mapping = mapping

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

    def diff(self, other):
        if not isinstance(other, self.__class__):
            return Edit(old=self, new=other)
        if self == other:
            return self.__class__()
        diffs = self.__class__()
        for k,v in self.items():
            if k not in other:
                diffs[k] = Deletion(old=v)
                continue
            if not equal(v, other[k]):
                if isinstance(v, BaseTree) and isinstance(other[k], BaseTree):
                    d = v.diff(other[k])
                    if len(d):
                        diffs[k] = d                    
                else:
                    diffs[k] = Edit(old=v, new=other[k])
        for k,v in other.items():
            if k not in self:
                diffs[k] = Insertion(new=v)
        return diffs

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
        import panel as pn
        if isinstance(v, (int, float)):
            return pn.indicators.Number(name=k, value=v, font_size="35pt", title_size="15pt",
                     format="{value}", sizing_mode="stretch_both")
        return pn.Column(f"## {k}",  f"{v}")

    def explorer(self, title="tree"):
        import panel as pn
        from ..visualizations import LabelTreeExplorer
        pn.extension()
        return LabelTreeExplorer(tree=self, label=title)

    def to_native(self):
        d = {}
        for k,v in self.items():
            if isinstance(v, BaseTree):
                d[k] = v.to_native()
            else:
                d[k] = v
        return d
