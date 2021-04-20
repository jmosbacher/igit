
import typing as ty
import hashlib
import pickle
from abc import ABC, abstractmethod
from .objects import IntervalTree, Interval
from .refs import ObjectRef, Commit, Tag

class BaseObjectStore(ABC):
    OTYPES = {
        "tree": IntervalTree,
        "commit": Commit,
        "tag": Tag,
        "blob": Interval,
    }
    
    OTYPE_NAMES = {v:k for k,v in OTYPES.items()}
    
    _store: ty.Mapping
        
    def __init__(self, store=None):
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
    
    def _hash_object(self, obj, otype):
        data = self._serialize(obj)
        key = self._hash(data)
        if key not in self._store:
            self._store[key] = data
        return ObjectRef(key=key, otype=otype, size=len(data))
    
    def hash_object(self, obj):
        otype = self.OTYPE_NAMES.get(type(obj), "blob")
        if otype == "tree":
            ivs = set(Interval(iv.begin, iv.end, self.hash_object(iv.data)) for iv in obj)
            obj = IntervalTree(ivs)
        return self._hash_object(obj, otype)

    def get(self, key):
        if isinstance(key, ObjectRef):
            key = key.key
        return self._store[key]
    
    def get_object(self, key, resolve_refs=True):
        obj = self._deserialize(self.get(key))
        if resolve_refs and isinstance(obj, IntervalTree):
            ivs = set()
            for iv in obj:
                if isinstance(iv.data, ObjectRef):
                    ivs.add(Interval(iv.begin, iv.end, self.get_object(iv.data.key)))
                else:
                    ivs.add(iv)
            obj = IntervalTree(ivs)
        return obj


    def get_ref(self, key):
        obj = self.get_object(key, resolve_refs=True)
        return self.hash_object(obj)
    
    @abstractmethod
    def _hash(self, data):
        pass
    
    @abstractmethod
    def _serialize(self, obj):
        pass
    
    @abstractmethod    
    def _deserialize(self, data):
        pass
    
class PickleObjectStore(BaseObjectStore):
    
    def _hash(self, data):
        return hashlib.sha1(data).hexdigest()
    
    def _serialize(self, obj):
        return pickle.dumps(obj)
        
    def _deserialize(self, data):
        return pickle.loads(data)
