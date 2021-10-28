import gridfs
import fsspec
import sys
import base64
import typing as ty

from zict import File, Func
from zict.common import ZictBase, close
from pymongo import MongoClient
from collections.abc import MutableMapping


from .common import BinaryStorage, IGitFunc, SubfolderMapper, DataCorruptionError
from ..models import TreeRef, BlobRef, ObjectRef, BaseObject, ObjectPacket
from ..serializers import SERIALIZERS
from ..trees import BaseTree
from ..hashing import HASH_FUNCTIONS
from ..compression import COMPRESSORS
from ..encryption import ENCRYPTORS
from ..constants import HASH_HOOK_NAME
from ..tokenize import tokenize



class ObjectStorage(ZictBase):
    d: ty.Mapping
    serializer: ty.Any
    suffix: str = ''

    def __init__(self,  d: BinaryStorage, serializer=None, suffix=''):
        self.d = d
        if isinstance(serializer, str):
            serializer = SERIALIZERS.get(serializer, None)
        self.serializer = serializer
        self.suffix = suffix

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

    @staticmethod
    def bytes_to_string(data):
        return base64.b64encode(data).decode()
    
    @staticmethod
    def string_to_bytes(data):
        return base64.b64decode(data)
    
    def serialize(self, obj):
        if self.serializer is None:
            return obj
        return self.serializer.serialize(obj)
    
    def deserialize(self, data):
        if self.serializer is None:
            return data
        return self.serializer.deserialize(data)

    def pack_object(self, obj):
        data = self.serialize(obj)
        pack = ObjectPacket(
            otype=obj.otype,
            content=self.bytes_to_string(data),
        )
        return pack
    
    def unpack_object(self, packet):
        data = self.string_to_bytes(packet.content)
        obj = self.deserialize(data)
        return obj

    def get_mapper(self):
        return IGitFunc(self.serialize, self.deserialize, self.d)

    def get(self, key, default=None):
        if key not in self.d:
            return default
        return self[key]

    def keys(self):
        return [k.strip(self.suffix) for k in self.d.keys()]

    def __getitem__(self, key):
        key = key + self.suffix
        return self.deserialize(self.d[key])

    def __setitem__(self, key, value):
        key = key + self.suffix
        self.d[key] = self.serialize(value)

    def __delitem__(self, key):
        key = key + self.suffix
        del self.d[key]

    def __iter__(self):
        for key in self.d.keys():
            yield key.strip(self.suffix)

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        key = key + self.suffix
        return key in self.d.keys()
        

class IGitObjectStoreMapper(SubfolderMapper):
    n: int
    sep: str
    # prefix = ""

    def __init__(self, d, n=2, sep="/", name="objects"):
        self.d = d
        self.n = n
        self.sep = sep
        self.name = name
        
    def long_key(self, key):
        return self.prefix + self.sep.join([key[:self.n], key[self.n:]])

    def short_key(self, key):
        if key.startswith(self.prefix):
            key = key[len(self.prefix):]
        return key[:self.n]+key[self.n+1:]

    def __str__(self):
        return "<ObjectStore: S[:%s]%sS[%s:] -> bytes>" % (
            str(self.n),
            self.sep,
            str(self.n),
            
        )

    __repr__ = __str__

class IGitObjectStore(ObjectStorage):
    verify: bool
    hash_func: ty.Callable

    def __init__(self, d: BinaryStorage, serializer=None, 
                verify=True):
        d = IGitObjectStoreMapper(d)
        super().__init__(d, serializer=serializer)
        self.verify = verify
        
        self.hash_func = tokenize

    def hash(self, obj)->str:
        hook = getattr(obj, HASH_HOOK_NAME, None)
        if hook is not None:
            obj = hook()
        return self.hash_func(obj)
    
    def get_ref(self, key, obj):
        size = sys.getsizeof(obj)
        if isinstance(obj, BaseTree):
            ref = TreeRef(key=key, tree_class=obj.__class__.__name__,
                 size=size)
        elif isinstance(obj, BaseObject):
            otype = obj.otype
            for class_ in ObjectRef.__subclasses__():
                if class_.otype == otype:
                    ref = class_(key=key, size=size)
                    break
            else:
                raise KeyError(otype)
        else:
            ref = BlobRef(key=key, size=size)
        return ref

    def hash_object(self, obj, save=True, as_ref=True):
        if isinstance(obj, BaseTree):
            new_obj = obj.__class__()
            for k,v in obj.items():
                new_obj[k] = self.hash_object(v, save=save)
            obj = new_obj
            # obj = obj.to_merkle_tree(self)
        key = self.hash(obj)
        if save:
            self.d[key] = self.serialize(obj)
        if as_ref:
            key = self.get_ref(key, obj)
        return key 

    def cat_object(self, key, deref=True, recursive=True):
        data = self.d[key]
        obj = self.deserialize(data)
        if deref and hasattr(obj, 'deref'):
            obj = obj.deref(self, recursive=recursive)
        if self.verify:
            key2 = self.hash_object(obj, save=False, as_ref=False)
            if key2 != key:
                
                raise DataCorruptionError(f"Looks like data has been corrupted or\
                     a different serializer was used. key: {key}, hash: {key2}")
        return obj
    
    def get(self, key, default=None):
        if key not in self.d:
            return default
        return self[key]

    def fuzzy_get(self, key):
        if key in self.d:
            return self.d[key]
        for k in self.d.keys():
            if key in k:
                return self.d[k]
        raise KeyError(key)
        
    def equal(self, *objs):
        return set([self.hash(obj) for obj in objs]) == 1

    def consistent_hash(self, obj):
        key1 = self.hash_object(obj, as_ref=False)
        key2 = self.hash_object(self.cat_object(key1), as_ref=False)
        return key1 == key2

def IGitModelStorage(model, d):
    return IGitFunc(lambda m: m.json().encode(), lambda data: model.parse_raw(data), d)


def hash_object(db, obj):
    if isinstance(obj, BaseTree):
        return obj.hash_tree(db)
    if isinstance(obj, list):
        return [hash_object(db, o) for o in obj]
    if isinstance(obj, dict):
        return {k:hash_object(db, v) for k,v in obj.items()}
    return db.hash_object(obj)