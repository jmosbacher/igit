import base64
import pickle
import hashlib
from abc import ABC, abstractmethod, abstractstaticmethod

class BaseObjectEncoder(ABC):

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
    def encode(self, data):
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


class PickleObjectEncoder(BaseObjectEncoder):

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
    def encode(data):
        return base64.b64encode(data).decode()
    
    @staticmethod
    def decode(data):
        return base64.b64decode(data)
    
    @staticmethod
    def compress(data):
        return data
    
    @staticmethod
    def decompress(data):
        return data

DEFAULT_ENCODER = "pickle"

ENCODERS = {
    "pickle": PickleObjectEncoder,
}