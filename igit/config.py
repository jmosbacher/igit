import fsspec
from pydantic import BaseModel

from .compression import COMPRESSORS
from .encryption import ENCRYPTORS
from .serializers import SERIALIZERS
from .storage import FunctionStorage, ObjectStorage, SubfolderStorage, \
                    SubfolderByKeyStorage, ContentAddressableStorage, \
                    PydanticModelStorage

from .refs import Refs
from .storage import SubfolderStorage
from .remotes import Remote
from .models import User, CommitRef, Tag


class Config(BaseModel):
    user: User = None
    main_branch: str = "master"
    HEAD: str = main_branch
    root_path: str = "file://./"
    igit_path: str = ".igit"
    tree_path: str = None

    serialization: str = "msgpack-dill"
    hash_func: str = "sha1"
    compression: str = "noop"
    encryption: str = "noop"
    encryption_kwargs: dict = None

    @classmethod
    def from_path(cls, path):
        with fsspec.open(path, "rb") as f:
            cfg = cls.parse_raw(f.read())
        return cfg

    def get_compressor(self):
        return COMPRESSORS[self.compression]

    def get_encryptor(self):
        kwargs = {}
        if self.encryption_kwargs is not None:
            kwargs.update(self.encryption_kwargs)
        return ENCRYPTORS[self.encryption](**kwargs)

    def get_serializer(self):
        return SERIALIZERS[self.serialization]

    def get_objects(self, store):
        if isinstance(store, str):
            store = fsspec.get_mapper(store)
        store = SubfolderStorage(store, name='objects')
        encryptor = self.get_encryptor()
        store = FunctionStorage(store,
                                encryptor.encrypt,
                                encryptor.decrypt, )

        compressor = self.get_compressor()
        if compressor is not None:
            store = FunctionStorage(store,
                                    compressor.compress,
                                    compressor.decompress)

        serializer = self.get_serializer()
        if serializer is not None:
            store = ObjectStorage(store, serializer=serializer)
        store = SubfolderByKeyStorage(store)
        store = ContentAddressableStorage(store)
        return store

    def get_index(self, store):
        store = SubfolderStorage(store, name='index')
        serializer = self.get_serializer()
        return ObjectStorage(store, serializer=serializer)


    def get_refs(self, store):
        commits_store = PydanticModelStorage(store, CommitRef)
        heads = SubfolderStorage(commits_store, "heads")
        tags_store = PydanticModelStorage(store, Tag)
        tags = SubfolderStorage(tags_store, "tags")
        remotes_store = PydanticModelStorage(store, Remote)
        remotes = SubfolderStorage(remotes_store, "remotes")
        return Refs(heads, tags, remotes)