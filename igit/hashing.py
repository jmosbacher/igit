import binascii
import hashlib
import json
from collections.abc import Iterable, Mapping

import dill
import numpy as np

hashers = []  # In decreasing performance order

# Timings on a largish array:
# - CityHash is 2x faster than MurmurHash
# - xxHash is slightly slower than CityHash
# - MurmurHash is 8x faster than SHA1
# - SHA1 is significantly faster than all other hashlib algorithms

try:
    import cityhash  # `python -m pip install cityhash`
except ImportError:
    pass
else:
    # CityHash disabled unless the reference leak in
    # https://github.com/escherba/python-cityhash/pull/16
    # is fixed.
    if cityhash.__version__ >= "0.2.2":

        def _hash_cityhash(buf):
            """
            Produce a 16-bytes hash of *buf* using CityHash.
            """
            h = cityhash.CityHash128(buf)
            return h.to_bytes(16, "little")

        hashers.append(_hash_cityhash)

try:
    import xxhash  # `python -m pip install xxhash`
except ImportError:
    pass
else:

    def _hash_xxhash(buf):
        """
        Produce a 8-bytes hash of *buf* using xxHash.
        """
        return xxhash.xxh64(buf).digest()

    hashers.append(_hash_xxhash)

try:
    import mmh3  # `python -m pip install mmh3`
except ImportError:
    pass
else:

    def _hash_murmurhash(buf):
        """
        Produce a 16-bytes hash of *buf* using MurmurHash.
        """
        return mmh3.hash_bytes(buf)

    hashers.append(_hash_murmurhash)


def _hash_sha1(buf):
    """
    Produce a 20-bytes hash of *buf* using SHA1.
    """
    return hashlib.sha1(buf).digest()


hashers.append(_hash_sha1)


def hash_buffer(buf, hasher=None):
    """
    Hash a bytes-like (buffer-compatible) object.  This function returns
    a good quality hash but is not cryptographically secure.  The fastest
    available algorithm is selected.  A fixed-length bytes object is returned.
    """
    if hasher is not None:
        try:
            return hasher(buf)
        except (TypeError, OverflowError):
            # Some hash libraries may have overly-strict type checking,
            # not accepting all buffers
            pass
    for hasher in hashers:
        try:
            return hasher(buf)
        except (TypeError, OverflowError):
            pass
    raise TypeError("unsupported type for hashing: %s" % (type(buf), ))


def hash_buffer_hex(buf, hasher=None):
    """
    Same as hash_buffer, but returns its result in hex-encoded form.
    """
    h = hash_buffer(buf, hasher)
    s = binascii.b2a_hex(h)
    return s.decode()


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
