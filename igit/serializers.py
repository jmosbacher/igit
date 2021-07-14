import base64
import pickle
import msgpack
import dill
import json
import hashlib
from abc import ABC, abstractmethod, abstractstaticmethod
from pydantic import BaseModel
from zict import File, Func
import pathlib
import msgpack_numpy as m
m.patch()


SERIALIZERS = {}


class DataCorruptionError(KeyError):
    pass

class EncoderMismatchError(TypeError):
    pass

class ObjectPacket(BaseModel):
    otype: str
    key: str
    content: str
    serializer: str
        
class BaseObjectSerializer(ABC):
    NAME: str
    key: bytes

    @abstractstaticmethod
    def serialize(obj):
        pass
    
    @abstractstaticmethod    
    def deserialize(data):
        pass
    
    @classmethod
    def get_mapper(cls, fs_mapper):
        if isinstance(fs_mapper, (str, pathlib.Path)):
            fs_mapper = File(fs_mapper, mode='a')
        mapper = Func(cls.serialize, cls.deserialize, fs_mapper)
        return mapper

class PickleObjectSerializer(BaseObjectSerializer):
    NAME = "pickle"

    @staticmethod
    def serialize(obj):
        return pickle.dumps(obj)
    
    @staticmethod
    def deserialize(data):
        return pickle.loads(data)


class DillObjectSerializer(BaseObjectSerializer):
    NAME = "dill"

    @staticmethod
    def serialize(obj):
        return dill.dumps(obj)
    
    @staticmethod
    def deserialize(data):
        return dill.loads(data)

class MsgpackObjectSerializer(BaseObjectSerializer):
    NAME = "msgpack"

    @staticmethod
    def serialize(obj):
        return msgpack.dumps(obj)

    @staticmethod
    def deserialize(data):
        return msgpack.loads(data)
 
class MsgpackDillObjectSerializer(BaseObjectSerializer):
    NAME = "msgpack-dill"

    @staticmethod
    def serialize(obj):
        try:
            return msgpack.dumps(obj)
        except:
            return dill.dumps(obj)
    
    @staticmethod
    def deserialize(data):
        try:
            return msgpack.loads(data)
        except:
            return dill.loads(data)


class JsonDillObjectSerializer(BaseObjectSerializer):
    NAME = "json-dill"

    @staticmethod
    def serialize(obj):
        try:
            return json.dumps(obj)
        except:
            return dill.dumps(obj)
    
    @staticmethod
    def deserialize(data):
        try:
            return json.loads(data)
        except:
            return dill.loads(data)


SERIALIZERS["pickle"] = PickleObjectSerializer
SERIALIZERS["dill"] = DillObjectSerializer
SERIALIZERS["msgpack"] = MsgpackObjectSerializer
SERIALIZERS["msgpack-dill"] = MsgpackDillObjectSerializer
SERIALIZERS["json-dill"] = JsonDillObjectSerializer
