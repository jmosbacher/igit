import gridfs
import fsspec
import sys
import base64
import typing as ty

from zict import File, Func
from zict.common import ZictBase, close
from pydantic import BaseModel
from pymongo import MongoClient
from collections.abc import MutableMapping

from ..models import TreeRef, BlobRef, ObjectRef, BaseObject
from ..serializers import SERIALIZERS
from ..trees import BaseTree
from ..hashing import HASH_FUNCTIONS
from ..compression import COMPRESSORS
from ..encryption import ENCRYPTORS
from ..constants import HASH_HOOK_NAME


class DataCorruptionError(KeyError):
    pass


class IGitFunc(Func):
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


class SubfolderMapper(ZictBase):
    name: str
    sep: str

    def __init__(self, name, d, sep="/"):
        self.name = name
        self.d = d
        self.sep = sep

    @property
    def fs(self):
        if hasattr(self.d, "fs"):
            return self.d.fs
        else:
            return self.d
    
    @property
    def root(self):
        root = self.prefix
        if hasattr(self.d, "root"):
            root = self.sep.join([self.d.root, root])
        return root

    @property
    def prefix(self):
        return  self.name + self.sep

    def long_key(self, key):
        if not key.startswith(self.prefix):
            key = (self.prefix + key.lstrip(self.sep)).lstrip(self.sep)
        return key

    def short_key(self, key):
        if key.startswith(self.prefix):
            key = key[len(self.prefix):]
        return key

    def __getitem__(self, key):
        key = self.long_key(key)
        return self.d[key]

    def __setitem__(self, key, value):
        key = self.long_key(key)
        self.d[key] = value

    def __contains__(self, key):
        key = self.long_key(key)
        return key in self.d

    def __delitem__(self, key):
        key = self.long_key(key)
        del self.d[key]

    def keys(self):
        for k in self.d.keys():
            if k and k.startswith(self.prefix):
                yield self.short_key(k)

    def values(self):
        for k,v in list(self.d.items()):
            if k and k.startswith(self.prefix):
                yield v

    def items(self):
        for k in self.d.keys():
            if k and k.startswith(self.prefix):
                yield self.short_key(k),self.d[k]

    def _do_update(self, items):
        self.d.update((self.long_key(k), v) for k, v in items if k)

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(list(self.keys()))

    def __str__(self):
        return "<Subfolder: %s%s -> %s>" % (
            self.sep,
            self.name,
            str(self.d),
        )

    __repr__ = __str__

    def flush(self):
        self.d.flush()

    def close(self):
        close(self.d)


class BinaryStorage(ZictBase):
    d: ty.Mapping    
    encryptor: ty.Any
    compressor: ty.Any

    def __init__(self, d, fs_options={}, encryptor=None,
                 compressor=None):
        if isinstance(d, str):
            d = fsspec.get_mapper(d, **fs_options)

        self.encryptor = encryptor

        if isinstance(compressor, str):
            compressor = COMPRESSORS.get(compressor, None)
        self.compressor = compressor

        self.d = self.get_mapper(d)

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

    def compress(self, data):
        if self.compressor is None:
            return data
        return self.compressor.compress(data)
    
    def decompress(self, data):
        if self.compressor is None:
            return data
        return self.compressor.decompress(data)

    def encrypt(self, data):
        if self.encryptor is None:
            return data
        return self.encryptor.encrypt(data)

    def decrypt(self, data):
        if self.encryptor is None:
            return data
        return self.encryptor.decrypt(data)

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

    def get_mapper(self, fs_mapper, **kwargs):
        if isinstance(fs_mapper, str):
            fs_mapper = fsspec.get_mapper(fs_mapper, **kwargs)
        mapper = IGitFunc(self.compress, self.decompress, fs_mapper)
        mapper = IGitFunc(self.encrypt, self.decrypt, mapper)
        return mapper

    def get_subfolder(self, name):
        return SubfolderMapper(self.d, name)
