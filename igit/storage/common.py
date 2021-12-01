import typing as ty
from collections.abc import MutableMapping

import fsspec


class DataCorruptionError(KeyError):
    pass


class ProxyStorage(MutableMapping):
    """MutableMapping that proxies its data
    access to another mapping. Meant to be subclassed
    to add interception functionality such as
    serialization/encryption/file access etc. 
    """
    d: ty.Mapping

    def __init__(self, d):
        self.d = d

    @classmethod
    def from_fsspec(cls, url, **fs_options):
        d = fsspec.get_mapper(url, **fs_options)
        return cls(d)

    @property
    def fs(self):
        if hasattr(self.d, "fs"):
            return self.d.fs
        else:
            return self.d

    @property
    def root(self):
        root = ""
        if hasattr(self.d, "root"):
            root = self.d.root
        return root

    def __getitem__(self, key):
        return self.d[key]

    def __setitem__(self, key, value):
        self.d[key] = value

    def get(self, key, default=None):
        if key not in self.d:
            return default
        return self.d.get(key)

    def keys(self):
        return self.d.keys()

    def __delitem__(self, key):
        del self.d[key]

    def __iter__(self):
        yield from self.d.keys()

    def __len__(self):
        return len(self.d)

    def __contains__(self, key):
        return key in self.d
