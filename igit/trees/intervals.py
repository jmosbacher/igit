import datetime
from collections.abc import Iterable, Mapping, MutableMapping
from numbers import Number

import pandas as pd
from intervaltree import Interval, IntervalTree

from ..diffs import Deletion, Diff, Edit, Insertion
from ..utils import equal
from .base import BaseTree
from .labels import LabelTree


class BaseIntervalTree(BaseTree):
    _tree: IntervalTree

    @staticmethod
    def compatible_keys(keys):
        for key in keys:
            if not isinstance(key, tuple):
                return False
            if not len(key) == 2:
                return False
            if not all([isinstance(x, (int, datetime.datetime)) for x in key]):
                return False
        return True

    @classmethod
    def from_dict(cls, d):
        ivs = [Interval(*k, v) for k, v in d.items()]
        return cls(IntervalTree(ivs))

    @classmethod
    def from_label_dict(cls, d):
        ivs = [Interval(*cls.label_to_key(k), v) for k, v in d.items()]
        return cls(IntervalTree(ivs))

    def add_group(self, name, group):
        self[name] = group

    @staticmethod
    def filter_keys(pattern):
        raise NotImplementedError

    @staticmethod
    def key_to_label(key):
        raise NotImplementedError

    @staticmethod
    def label_to_key(label):
        raise NotImplementedError

    @staticmethod
    def _validate_itype(begin, end):
        raise NotImplementedError

    def to_label_dict(self):
        return {
            self.key_to_label((iv.begin, iv.end)): iv.data
            for iv in sorted(self._tree)
        }

    def to_dict(self):
        return {(iv.begin, iv.end): iv.data for iv in sorted(self._tree)}

    def __init__(self, tree=None, *args, **kwargs):
        if tree is None:
            tree = IntervalTree()
        elif isinstance(tree, IntervalTree):
            tree = tree
        elif isinstance(tree, BaseIntervalTree):
            tree = tree._tree
        else:
            raise TypeError("tree must be an instance of IntervalTree.")
        self._tree = tree

    def __getitem__(self, key):
        if isinstance(key, str):
            key = self.label_to_key(key)
        if isinstance(key, Number):
            return self.value(key)
        elif isinstance(key, tuple) and len(key) == 2:
            return self.overlap_content(*key)
        elif isinstance(key, Iterable):
            return self.values_at(key)
        elif isinstance(key, slice):
            start = key.start or self.start
            stop = key.stop or self.end
            if key.step is None:
                return self.overlap(key.start, key.stop)
            else:
                return self.values_at(range(start, stop, key.step))
        raise KeyError('No overlapping data found.')

    @property
    def start(self):
        return self._tree.begin()

    @property
    def end(self):
        return self._tree.end()

    def __setitem__(self, key, value):
        if isinstance(key, str):
            key = self.label_to_key(key)
        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
        elif isinstance(key, tuple):
            if len(key) == 2:
                start, stop = key
                step = None
            elif len(key) == 3:
                start, stop, step = key
            else:
                raise ValueError("Setting intervals with tuple must be  \
                            of form (start, end) or (start, end, step)")
        else:
            raise TypeError(
                "Wrong type. Setting intervals can only be done using a \
                            slice or tuple of (start, end) or (start, end, step)"
            )
        if start is None:
            start = self.start
        if stop is None:
            stop = self.end
        if step is None:
            self.set_interval(start, stop, value)
        else:
            indices = list(range(start, stop, step))
            for begin, end, val in zip(indices[:-1], indices[1:], value):
                self.set_interval(begin, end, val)

    def __delitem__(self, key):
        if isinstance(key, str):
            key = self.label_to_key(key)
        elif isinstance(key, tuple) and len(key) == 2:
            self._tree.chop(*key)
        elif isinstance(key, slice):
            self._tree.chop(key.start, key.end)
        else:
            raise TypeError("Must pass a tuple of (begin,end) or slice.")

    def keys(self):
        for iv in sorted(self._tree):
            yield iv.begin, iv.end

    def labels(self):
        return map(self.key_to_label, self.keys())

    def items(self):
        for iv in sorted(self._tree):
            yield (iv.begin, iv.end), iv.data

    def values(self):
        for iv in sorted(self._tree):
            yield iv.data

    def __iter__(self):
        return self.keys()

    def __len__(self):
        return len(self._tree)

    def __bool__(self):
        return bool(len(self._tree))

    def __contains__(self, key):
        return bool(self[key])

    def __getstate__(self):
        return tuple(sorted([tuple(iv) for iv in self._tree]))

    def __setstate__(self, d):
        ivs = [Interval(*iv) for iv in d]
        self._tree = IntervalTree(ivs)

    def overlap(self, begin, end):
        begin, end = self._validate_itype(begin, end)
        hits = sorted(self._tree.overlap(begin, end))
        return [
            Interval(max(iv.begin, begin), min(iv.end, end), iv.data)
            for iv in hits
        ]

    def overlap_content(self, begin, end):
        hits = sorted(self._tree.overlap(begin, end))
        if len(hits) == 1:
            return hits[0].data
        return [hit.data for hit in hits]

    def value(self, index):
        index, = self._validate_itype(index)
        hits = sorted(self._tree.at(index))
        if not hits:
            raise KeyError(f'No data overlapps {index}')
        if len(hits) == 1:
            return hits[0].data
        return hits

    def values_at(self, indices):
        indices = self._validate_itype(*indices)
        return [self.value(i) for i in indices]

    def set_interval(self, begin, end, value):
        begin, end = self._validate_itype(begin, end)
        self._tree.chop(begin, end)
        self._tree.addi(begin, end, value)

    def to_df(self, title="tree"):
        import pandas as pd
        ivs = []

        for (begin, end), data in self.items():
            if isinstance(data, BaseTree):
                data = float("nan")
            interval = {
                "label": f"{begin}-{end}",
                "begin": begin,
                "parameter": title,
                "mid": (begin + end) / 2,
                "end": end,
                "data": data
            }
            ivs.append(interval)
        return pd.DataFrame(ivs)

    def to_native(self):
        ivs = []
        for (begin, end), data in self.items():
            if isinstance(data, BaseTree):
                iv = Interval(begin, end, data.to_native())
            else:
                iv = Interval(begin, end, data)
            ivs.append(iv)
        return IntervalTree(ivs)

    def explorer(self, title="tree"):
        import panel as pn
        pn.extension()
        from ..visualizations import IntervalTreeExplorer
        return IntervalTreeExplorer(tree=self, label=title)

    def diff(self, other):
        if not isinstance(other, self.__class__):
            return Edit(old=self, new=other)
        if self == other:
            return self.__class__()
        u = self._tree.union(other._tree)
        u.split_overlaps()
        u.merge_equals()
        diffs = self.__class__()
        for iv in u:
            k = iv.begin, iv.end
            if k not in self:
                diffs[k] = Insertion(new=other[k])
            elif k not in other:
                diffs[k] = Deletion(old=self[k])
            elif isinstance(self[k], BaseTree) and isinstance(
                    other[k], BaseTree):
                d = self[k].diff(other[k])
                if len(d):
                    diffs[k] = d
            elif not equal(self[k], other[k]):
                diffs[k] = Edit(old=self[k], new=other[k])
        return diffs


class IntIntervalTree(BaseIntervalTree):
    def filter_keys(self, pattern):
        if isinstance(pattern, tuple):
            begin, end = pattern
        elif isinstance(pattern, slice):
            begin, end = pattern.start, pattern.stop
        else:
            raise TypeError(
                'pattern must be an interval defined by tuple or slice.')
        return [(iv.begin, iv.end) for iv in self.overlap(begin, end)]

    @staticmethod
    def key_to_label(key):
        return f"{key[0]}-{key[1]}"

    @staticmethod
    def label_to_key(label):
        return tuple(map(int, label.split("-")))

    def to_label_dict(self):
        return {f"{iv.begin}-{iv.end}": iv.data for iv in sorted(self._tree)}

    def _validate_itype(self, *args):
        return tuple(int(arg) for arg in args)


class TimeIntervalTree(BaseIntervalTree):
    unit: str

    def __init__(self, *args, unit='s', **kwargs):
        self.unit = unit
        super().__init__(*args, **kwargs)

    def filter_keys(self, pattern):
        if isinstance(pattern, tuple):
            begin, end = pattern
        elif isinstance(pattern, slice):
            begin, end = pattern.start, pattern.stop
        else:
            raise TypeError(
                'pattern must be an interval defined by tuple or slice.')
        return [(iv.begin, iv.end) for iv in self.overlap(begin, end)]

    @staticmethod
    def key_to_label(key):
        return f"({key[0]})-({key[1]})"

    @staticmethod
    def label_to_key(label):
        return tuple(map(pd.to_datetime, label.strip('()').split(")-(")))

    def _validate_itype(self, *args):
        return tuple(pd.to_datetime(arg, unit=self.unit) for arg in args)


def collect_intervals(tree, parent=(), merge_names=True, join_char="_"):
    ivs = []
    if isinstance(tree, BaseIntervalTree):
        for (begin, end), data in tree.items():
            if merge_names:
                label = join_char.join(parent)
            else:
                label = parent
            if isinstance(data, BaseTree):
                name = parent + (str((begin, end)), )
                ivs.extend(
                    collect_intervals(data,
                                      parent=name,
                                      merge_names=merge_names,
                                      join_char=join_char))
                data = float('nan')

            interval = {
                "label": label,
                "begin": begin,
                "mid": (begin + end) / 2,
                "end": end,
                "data": data
            }
            ivs.append(interval)

    elif isinstance(tree, LabelTree):
        for k, v in tree.items():
            name = parent + (k, )
            if isinstance(v, BaseTree):
                ivs.extend(
                    collect_intervals(v,
                                      parent=name,
                                      merge_names=merge_names,
                                      join_char=join_char))
    return ivs
