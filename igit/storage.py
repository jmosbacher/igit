import typing as ty
import fsspec
from zict import File, Func
from zict.common import ZictBase, close
from pydantic import BaseModel

from .serializers import SERIALIZERS
from .hashing import HASH_FUNCTIONS
from .compression import COMPRESSORS
from .encryption import ENCRYPTORS
from .settings import DEFAULT_SERIALIZER, DEFAULT_ENCRYPTION, DEFAULT_COMPRESSION, DEFAULT_HASH


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
                 compressor=DEFAULT_COMPRESSION):
        if isinstance(d, str):
            d = fsspec.get_mapper(d, **fs_options)

        if isinstance(encryptor, bytes):
            encryptor_key = encryptor
            encryptor = ENCRYPTORS.get(DEFAULT_ENCRYPTION, None)
            if encryptor is not None:
                encryptor = encryptor(encryptor_key)
            
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
        if k not in self.d:
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

class ObjectPacket(BaseModel):
    otype: str
    content: str
        
class ObjectStorage(ZictBase):
    d: ty.Mapping
    serializer: ty.Any

    def __init__(self,  d: BinaryStorage, serializer=DEFAULT_SERIALIZER):
        self.d = d
        if isinstance(serializer, str):
            serializer = SERIALIZERS.get(serializer, None)
        self.serializer = serializer

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
        return self.deserialize(self.d[key])

    def keys(self):
        return list(self.d.keys())

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.d[key] = self.serialize(value)

    def __delitem__(self, key):
        del self.d[key]

    def __iter__(self):
        yield from self.d.keys()

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
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

    def __init__(self, d: BinaryStorage, serializer=DEFAULT_SERIALIZER, 
                 hash_func=DEFAULT_HASH, verify=True):
        d = IGitObjectStoreMapper(d)
        super().__init__(d, serializer=serializer)
        self.verify = verify
        if isinstance(hash_func, str):
            hash_func = HASH_FUNCTIONS.get(hash_func, None)
        if hash_func is None:
            hash_func = lambda data: str(hash(data))
        self.hash_func = hash_func

    def hash(self, data):
        return self.hash_func(data)
    
    def hash_object(self, obj, save=True):
        data = self.serialize(obj)
        key = self.hash(data)
        if save and key not in self.d:
            self.d[key] = data
        return key

    def cat_object(self, key):
        data = self.d[key]
        if self.verify:
            if self.hash(data) != key:
                raise DataCorruptionError("Looks like data has been corrupted or\
                     a different serializer was used.")
        obj = self.deserialize(data)
        return obj
    
    def get(self, key, default=None):
        if key not in self.d:
            return default
        return self.cat_object(key)

def IGitModelStorage(model, d):
    return IGitFunc(lambda m: m.json().encode(), lambda data: model.parse_raw(data), d)
