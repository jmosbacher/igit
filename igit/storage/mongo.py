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


class GFSMapping(MutableMapping):
    _fs = None
    def __init__(self, db: str, **kwargs):
        self.db = db
        self.connection_kwargs = kwargs

    @property
    def fs(self):
        if self._fs is None:
            client = MongoClient(**self.connection_kwargs)
            db = client[self.db]
            self._fs = gridfs.GridFS(db)
        return self._fs

    def __getitem__(self, key):
        if self.fs.exists({"filename": key}):
            return self.fs.find_one({"filename": key}).read()
        else:
            raise KeyError(key)
            
    def __setitem__(self, key, value):
        if self.fs.exists({"filename": key}):
            del self[key]
        self.fs.put(value, filename=key)

    def __getattr__(self, key):
        return self[key]

    def __delitem__(self, key):
        if self.fs.exists({"filename": key}):
            _id = self.fs.find_one({"filename": key})._id
            self.fs.delete(_id)
        else:
            raise KeyError(key)
            
    def keys(self):
        return self.fs.list()
        
    def __dir__(self):
        return self.keys()
        
    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(self.keys())
    
    def __getstate__(self):
        return {"db": self.db, "connection_kwargs": self.connection_kwargs}

    def __setstate__(self, d):
        self.db = d["db"]
        self.connection_kwargs = d["connection_kwargs"]