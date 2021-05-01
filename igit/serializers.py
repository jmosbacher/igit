import base64
import pickle
import msgpack
import hashlib
from abc import ABC, abstractmethod, abstractstaticmethod
from pydantic import BaseModel
from zict import File, Func
import pathlib

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
    def hash(data):
        pass
    
    @abstractstaticmethod
    def serialize(obj):
        pass
    
    @abstractstaticmethod    
    def deserialize(data):
        pass
    
    @abstractstaticmethod
    def encode(cls, data):
        pass
    
    @abstractstaticmethod
    def decode(data):
        pass

    @abstractstaticmethod
    def compress(data):
        pass
    
    @abstractstaticmethod
    def decompress(data):
        pass
    
    @abstractstaticmethod
    def encrypt(data, key):
        pass
    
    @abstractstaticmethod
    def decrypt(data, key):
        pass

    @classmethod
    def hash_object(cls, obj, key=None):
        data = cls.serialize(obj)
        key = cls.hash(data)
        if key is not None:
            data = cls.encrypt(data)
        data = cls.compress(data)
        return key, data

    @classmethod
    def cat_object(cls, data, verify=None, key=None):
        data = cls.decompress(data)
        if key is not None:
            data = cls.decrypt(data)
        if verify:
            ha = cls.hash(data)
            if ha != verify:
                raise DataCorruptionError("Looks like data has been corrupted or\
                     a different serializer was used.")
        obj = cls.deserialize(data)
        return obj

    @classmethod
    def pack_object(cls, obj, key=None):
        key,data = cls.hash_object(obj, key=key)
        pack = ObjectPacket(
            otype=obj.otype,
            key=key,
            content=cls.bytes_to_string(data),
            serializer=cls.NAME,
        )
        return pack

    @classmethod
    def unpack_object(cls, packet, verify=None, key=None):
        if packet.serializer != cls.NAME:
            raise EncoderMismatchError(f"You are trying to use serializer\
                 {cls.NAME} to unpack a package packed with serializer {packet.serializer}.")
        data = cls.string_to_bytes(packet.content)
        obj = cls.cat_object(data, verify=verify, key=key)
        return obj

    @classmethod
    def get_mapper(cls, fs_mapper, verify=None, key=None):
        if isinstance(fs_mapper, (str, pathlib.Path)):
            fs_mapper = File(fs_mapper, mode='a')
        mapper = Func(cls.compress, cls.decompress, fs_mapper)
        mapper = Func(cls.serialize, cls.deserialize, mapper)
        return mapper

class PickleObjectSerializer(BaseObjectSerializer):
    NAME = "pickle"

    @staticmethod
    def hash(data):
        return hashlib.sha1(data).hexdigest()
    
    @staticmethod
    def serialize(obj):
        return pickle.dumps(obj)
    
    @staticmethod
    def deserialize(data):
        return pickle.loads(data)

    @staticmethod
    def bytes_to_string(data):
        return base64.b64encode(data).decode()
    
    @staticmethod
    def string_to_bytes(data):
        return base64.b64decode(data)
    
    @staticmethod
    def compress(data):
        return data
    
    @staticmethod
    def decompress(data):
        return data

    @staticmethod
    def encrypt(data, key):
        return data
    
    @staticmethod
    def decrypt(data, key):
        return data

    @staticmethod
    def verify(data, key):
        return data

class MsgpackObjectSerializer(PickleObjectSerializer):
    NAME = "msgpack"

    @staticmethod
    def hash(data):
        return hashlib.sha1(data).hexdigest()
    
    @staticmethod
    def serialize(obj):
        try:
            return msgpack.dumps(obj)
        except:
            return pickle.dumps(obj)
    
    @staticmethod
    def deserialize(data):
        try:
            return msgpack.loads(data)
        except:
            return pickle.loads(data)


SERIALIZERS["pickle"] = PickleObjectSerializer
SERIALIZERS["msgpack"] = MsgpackObjectSerializer

