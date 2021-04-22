
import typing as ty
from abc import ABC, abstractmethod, abstractstaticmethod
from .objects import IntervalTree, Interval, ObjectPacket
from .refs import ObjectRef, Commit, Tag
from .trees import BaseTree
from .encoders import ENCODERS, DEFAULT_ENCODER

OTYPES = {
    "tree": BaseTree,
    "commit": Commit,
    "tag": Tag,
    }

class ObjectStore:
    "thin wrapper around a mapping str->bytes"
    _store: ty.Mapping
    
        
    def __init__(self, store=None, encoder=None):
        if store is None:
            store = self.init_storage(store)
        if not isinstance(store, ty.Mapping):
            raise TypeError("store must be a Mapping.")
        self._store = store
    
    def __getitem__(self, key):
        return self.get_object(key)

    def keys(self):
        return self._store.keys()
    
    def items(self):
        for key in self.keys():
            yield key, self.get_object(key) 

    def init_storage(self, store: ty.Mapping=None):
        if store is None:
            store = {}
        return store
    
    def _hash_object(self, obj, otype, encoder):
        enc = ENCODERS[encoder]
        data = enc.serialize(obj)
        size = len(data)
        key = enc.hash(data)
        if key not in self._store:
            self._store[key] = enc.compress(data)
        return ObjectRef(key=key, otype=otype, size=size, encoder=encoder)
    
    def hash_object(self, obj, encoder=None):
        for otype, class_ in OTYPES.items():
            if isinstance(obj, class_):
                break
        else:
            otype = "blob"
        if otype == "tree":
            enc = obj.encoder
            obj = obj.to_dict()
            obj = {k: self.hash_object(v, enc) for k,v in obj.items()}
        if encoder is None:
            encoder = DEFAULT_ENCODER
        return self._hash_object(obj, otype, encoder)

    def get(self, ref):
        if isinstance(ref, ObjectRef):
            key = ref.key
        else:
            key = ref
        if key in self._store:
            return self._store[key]
        for k in self.keys():
            if k.startswith(key):
                return self._store[k]
        raise KeyError(f"{key} not found.")
            
    def get_object(self, ref, otype='blob', encoder=None, resolve_refs=True):
        if isinstance(ref, ObjectRef):
            encoder = ENCODERS[ref.encoder]
        elif encoder is None:
            encoder = ENCODERS[DEFAULT_ENCODER]
        else:
            encoder = ENCODERS[encoder]
        data = encoder.decompress(self.get(ref))
        obj = encoder.deserialize(data)
        if isinstance(ref, ObjectRef):
            otype = ref.otype
        if resolve_refs and otype=='tree':
            d = {}
            for k,v in obj.items():
                if isinstance(v, ObjectRef):
                    d[k] = self.get_object(v)
                else:
                    d[k] = v
            obj = BaseTree.instance_from_dict(d)
        return obj

    def get_ref(self, key, encoder=None):
        obj = self.get_object(key, encoder=encoder, resolve_refs=True)
        return self.hash_object(obj, encoder=encoder)
    
    def get_object_packet(self, ref, encoder=None):
        if encoder is None:
            encoder = DEFAULT_ENCODER
        enc = ENCODERS[encoder]
        obj = ObjectPacket(
            otype=ref.otype,
            content=enc.encode(self.get(ref)),
            encoder=encoder,
        )
        return obj

    def object_from_packet(self, packet):
        encoder = ENCODERS[packet.encoder]
        data = encoder.decode(packet.content)
        obj = encoder.deserialize(data)
        return obj