import sys
import typing as ty

from collections.abc import MutableMapping

from .common import ProxyStorage, DataCorruptionError
from ..models import TreeRef, BlobRef, ObjectRef, BaseObject
from ..trees import BaseTree
from ..tokenize import tokenize


class ContentAddressableStorage(ProxyStorage):
    verify: bool
    hash_func: ty.Callable

    def __init__(self, d: MutableMapping, 
                 verify=True,):
        self.d = d
        self.verify = verify

    def hash(self, obj)->str:
        return tokenize(obj)
    
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
        key = self.hash(obj)
        if save:
            self.d[key] = obj
        if as_ref:
            key = self.get_ref(key, obj)
        return key 

    def cat_object(self, key, deref=True, recursive=True):
        obj = self.d[key]
        if deref and hasattr(obj, 'deref'):
            obj = obj.deref(self, recursive=recursive)
        if self.verify:
            key2 = self.hash_object(obj, save=False, as_ref=False)
            if key2 != key:
                raise DataCorruptionError(f"Looks like data has been corrupted or\
                     a different serializer/encryption was used. key: {key}, hash: {key2}")
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