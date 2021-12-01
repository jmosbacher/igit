import base64
import typing as ty
from collections.abc import MutableMapping

from ..models import ObjectPacket
from ..serializers import SERIALIZERS
from .common import ProxyStorage


class ObjectStorage(ProxyStorage):
    d: ty.Mapping
    serializer: ty.Any
    suffix: str = ''

    def __init__(self, d: MutableMapping, serializer=None, suffix=''):
        self.d = d
        if isinstance(serializer, str):
            serializer = SERIALIZERS.get(serializer, None)
        self.serializer = serializer
        self.suffix = suffix

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
