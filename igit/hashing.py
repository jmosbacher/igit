import hashlib
import json
import numpy as np
import dill
from collections.abc import Mapping, Iterable

HASH_FUNCTIONS = {}

class NumpyJSONEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types
    Edited from mpl3d: mpld3/_display.py
    """

    def default(self, obj):
        if hasattr(obj, 'json'):
            return obj.json()
        try:
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return [self.default(item) for item in iterable]
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def hashablize(obj):
    """Convert a container hierarchy into one that can be hashed.
    See http://stackoverflow.com/questions/985294
    """
    if hasattr(obj, "_igit_hash_") and callable(obj._igit_hash_):
        return obj._igit_hash_()

    try:
        hash(obj)
    except TypeError:
        if isinstance(obj, Mapping):
            return tuple((k, hashablize(v)) for (k, v) in sorted(obj.items()))
        elif isinstance(obj, np.ndarray):
            return tuple(hashablize(o) for o in obj.tolist())
        elif isinstance(obj, Iterable):
            return tuple(hashablize(o) for o in obj)
        else:
            raise TypeError("Can't hashablize object of type %r" % type(obj))
    else:
        return obj

def sha1_hash(data):
    return hashlib.sha1(data).hexdigest()

def container_hash(obj):
    if hasattr(obj, "_igit_hash_") and callable(obj._igit_hash_):
        return obj._igit_hash_()
    try:
        hashable = hashablize(obj)
        data = json.dumps(hashable, cls=NumpyJSONEncoder).encode()
    except:
        data = dill.dumps(obj)
    return sha1_hash(data)

HASH_FUNCTIONS["sha1"] = container_hash