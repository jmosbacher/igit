import base64
import hashlib
import json
import pathlib
import pickle
from abc import ABC, abstractmethod, abstractstaticmethod

import dill
import msgpack
import msgpack_numpy as m
from pydantic import BaseModel
from zict import File, Func

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
    suffix: str = ''

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        SERIALIZERS[cls.NAME] = cls

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


class NoopSerializer(BaseObjectSerializer):
    NAME = None

    @staticmethod
    def serialize(obj):
        return obj

    @staticmethod
    def deserialize(data):
        return data


SERIALIZERS[""] = NoopSerializer


class JsonObjectSerializer(BaseObjectSerializer):
    NAME = "json"

    @staticmethod
    def serialize(obj):
        return json.dumps(obj).encode()

    @staticmethod
    def deserialize(data):
        return json.loads(data)


class PickleObjectSerializer(BaseObjectSerializer):
    NAME = "pickle"
    suffix: str = '.pkl'

    @staticmethod
    def serialize(obj):
        return pickle.dumps(obj)

    @staticmethod
    def deserialize(data):
        return pickle.loads(data)


class DillObjectSerializer(BaseObjectSerializer):
    NAME = "dill"
    suffix: str = '.dill'

    @staticmethod
    def serialize(obj):
        return dill.dumps(obj)

    @staticmethod
    def deserialize(data):
        return dill.loads(data)


class MsgpackObjectSerializer(BaseObjectSerializer):
    NAME = "msgpack"
    suffix: str = '.msg'

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
            return json.dumps(obj).encode()
        except:
            return dill.dumps(obj)

    @staticmethod
    def deserialize(data):
        try:
            return json.loads(data)
        except:
            return dill.loads(data)
