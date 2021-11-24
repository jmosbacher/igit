import datetime
import inspect
import os
import pickle
import threading
import uuid
from collections import OrderedDict
from concurrent.futures import Executor
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from functools import partial
from hashlib import md5
from numbers import Number
from operator import getitem
from typing import Iterator, Mapping, Set

from packaging.version import parse as parse_version
from tlz import curry, groupby, identity, merge
from tlz.functoolz import Compose

from .hashing import hash_buffer_hex
from .utils import Dispatch


def tokenize(*args, **kwargs):
    """Deterministic token
    >>> tokenize([1, 2, '3'])
    '7d6a880cd9ec03506eee6973ff551339'
    >>> tokenize('Hello') == tokenize('Hello')
    True
    """
    if kwargs:
        args = args + (kwargs,)
    return md5(str(tuple(map(normalize_token, args))).encode()).hexdigest()

def are_equal(a,b):
    return tokenize(a) == tokenize(b)

normalize_token = Dispatch()
normalize_token.register(
    (
        int,
        float,
        str,
        bytes,
        type(None),
        type,
        slice,
        complex,
        type(Ellipsis),
        datetime.date,
    ),
    identity,
)


@normalize_token.register(dict)
def normalize_dict(d):
    return normalize_token(sorted(d.items(), key=str))


@normalize_token.register(OrderedDict)
def normalize_ordered_dict(d):
    return type(d).__name__, normalize_token(list(d.items()))


@normalize_token.register(set)
def normalize_set(s):
    return normalize_token(sorted(s, key=str))


@normalize_token.register((tuple, list))
def normalize_seq(seq):
    def func(seq):
        try:
            return list(map(normalize_token, seq))
        except RecursionError:
            return str(uuid.uuid4())

    return type(seq).__name__, func(seq)


@normalize_token.register(range)
def normalize_range(r):
    return list(map(normalize_token, [r.start, r.stop, r.step]))


@normalize_token.register(object)
def normalize_object(o):
    method = getattr(o, "__igit_tokenize__", None)
    if method is not None:
        return method()
    method = getattr(o, "__dask_tokenize__", None)
    if method is not None:
        return method()
    return normalize_function(o) if callable(o) else uuid.uuid4().hex


function_cache = {}
function_cache_lock = threading.Lock()


def normalize_function(func):
    try:
        return function_cache[func]
    except KeyError:
        result = _normalize_function(func)
        if len(function_cache) >= 500:  # clear half of cache if full
            with function_cache_lock:
                if len(function_cache) >= 500:
                    for k in list(function_cache)[::2]:
                        del function_cache[k]
        function_cache[func] = result
        return result
    except TypeError:  # not hashable
        return _normalize_function(func)


def _normalize_function(func):
    if isinstance(func, Compose):
        first = getattr(func, "first", None)
        funcs = reversed((first,) + func.funcs) if first else func.funcs
        return tuple(normalize_function(f) for f in funcs)
    elif isinstance(func, (partial, curry)):
        args = tuple(normalize_token(i) for i in func.args)
        if func.keywords:
            kws = tuple(
                (k, normalize_token(v)) for k, v in sorted(func.keywords.items())
            )
        else:
            kws = None
        return (normalize_function(func.func), args, kws)
    else:
        try:
            result = pickle.dumps(func, protocol=0)
            if b"__main__" not in result:  # abort on dynamic functions
                return result
        except Exception:
            pass
        try:
            import cloudpickle

            return cloudpickle.dumps(func, protocol=0)
        except Exception:
            return str(func)


@normalize_token.register_lazy("pandas")
def register_pandas():
    import pandas as pd

    PANDAS_GT_130 = parse_version(pd.__version__) >= parse_version("1.3.0")

    @normalize_token.register(pd.Index)
    def normalize_index(ind):
        values = ind.array
        return [ind.name, normalize_token(values)]

    @normalize_token.register(pd.MultiIndex)
    def normalize_index(ind):
        codes = ind.codes
        return (
            [ind.name]
            + [normalize_token(x) for x in ind.levels]
            + [normalize_token(x) for x in codes]
        )

    @normalize_token.register(pd.Categorical)
    def normalize_categorical(cat):
        return [normalize_token(cat.codes), normalize_token(cat.dtype)]

    @normalize_token.register(pd.arrays.PeriodArray)
    @normalize_token.register(pd.arrays.DatetimeArray)
    @normalize_token.register(pd.arrays.TimedeltaArray)
    def normalize_period_array(arr):
        return [normalize_token(arr.asi8), normalize_token(arr.dtype)]

    @normalize_token.register(pd.arrays.IntervalArray)
    def normalize_interval_array(arr):
        return [
            normalize_token(arr.left),
            normalize_token(arr.right),
            normalize_token(arr.closed),
        ]

    @normalize_token.register(pd.Series)
    def normalize_series(s):
        return [
            s.name,
            s.dtype,
            normalize_token(s._values),
            normalize_token(s.index),
        ]

    @normalize_token.register(pd.DataFrame)
    def normalize_dataframe(df):
        mgr = df._data

        if PANDAS_GT_130:
            # for compat with ArrayManager, pandas 1.3.0 introduced a `.arrays`
            # attribute that returns the column arrays/block arrays for both
            # BlockManager and ArrayManager
            data = list(mgr.arrays)
        else:
            data = [block.values for block in mgr.blocks]
        data.extend([df.columns, df.index])
        return list(map(normalize_token, data))

    @normalize_token.register(pd.api.extensions.ExtensionArray)
    def normalize_extension_array(arr):
        import numpy as np

        return normalize_token(np.asarray(arr))

    # Dtypes
    @normalize_token.register(pd.api.types.CategoricalDtype)
    def normalize_categorical_dtype(dtype):
        return [normalize_token(dtype.categories), normalize_token(dtype.ordered)]

    @normalize_token.register(pd.api.extensions.ExtensionDtype)
    def normalize_period_dtype(dtype):
        return normalize_token(dtype.name)


@normalize_token.register_lazy("numpy")
def register_numpy():
    import numpy as np

    @normalize_token.register(np.ndarray)
    def normalize_array(x):
        if not x.shape:
            return (x.item(), x.dtype)
        if hasattr(x, "mode") and getattr(x, "filename", None):
            if hasattr(x.base, "ctypes"):
                offset = (
                    x.ctypes._as_parameter_.value - x.base.ctypes._as_parameter_.value
                )
            else:
                offset = 0  # root memmap's have mmap object as base
            if hasattr(
                x, "offset"
            ):  # offset numpy used while opening, and not the offset to the beginning of the file
                offset += getattr(x, "offset")
            return (
                x.filename,
                os.path.getmtime(x.filename),
                x.dtype,
                x.shape,
                x.strides,
                offset,
            )
        if x.dtype.hasobject:
            try:
                try:
                    # string fast-path
                    data = hash_buffer_hex(
                        "-".join(x.flat).encode(
                            encoding="utf-8", errors="surrogatepass"
                        )
                    )
                except UnicodeDecodeError:
                    # bytes fast-path
                    data = hash_buffer_hex(b"-".join(x.flat))
            except (TypeError, UnicodeDecodeError):
                try:
                    data = hash_buffer_hex(pickle.dumps(x, pickle.HIGHEST_PROTOCOL))
                except Exception:
                    # pickling not supported, use UUID4-based fallback
                    data = uuid.uuid4().hex
        else:
            try:
                data = hash_buffer_hex(x.ravel(order="K").view("i1"))
            except (BufferError, AttributeError, ValueError):
                data = hash_buffer_hex(x.copy().ravel(order="K").view("i1"))
        return (data, x.dtype, x.shape, x.strides)

    @normalize_token.register(np.matrix)
    def normalize_matrix(x):
        return type(x).__name__, normalize_array(x.view(type=np.ndarray))

    normalize_token.register(np.dtype, repr)
    normalize_token.register(np.generic, repr)

    @normalize_token.register(np.ufunc)
    def normalize_ufunc(x):
        try:
            name = x.__name__
            if getattr(np, name) is x:
                return "np." + name
        except AttributeError:
            return normalize_function(x)


@normalize_token.register_lazy("scipy")
def register_scipy():
    import scipy.sparse as sp

    def normalize_sparse_matrix(x, attrs):
        return (
            type(x).__name__,
            normalize_seq((normalize_token(getattr(x, key)) for key in attrs)),
        )

    for cls, attrs in [
        (sp.dia_matrix, ("data", "offsets", "shape")),
        (sp.bsr_matrix, ("data", "indices", "indptr", "blocksize", "shape")),
        (sp.coo_matrix, ("data", "row", "col", "shape")),
        (sp.csr_matrix, ("data", "indices", "indptr", "shape")),
        (sp.csc_matrix, ("data", "indices", "indptr", "shape")),
        (sp.lil_matrix, ("data", "rows", "shape")),
    ]:
        normalize_token.register(cls, partial(normalize_sparse_matrix, attrs=attrs))

    @normalize_token.register(sp.dok_matrix)
    def normalize_dok_matrix(x):
        return type(x).__name__, normalize_token(sorted(x.items()))
