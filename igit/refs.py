from typing import Mapping

from .models import CommitRef, Tag
from .mappers import SubfolderMapper
from .serializers import SERIALIZERS
from .remotes import Remote
from .settings import DEFAULT_SERIALIZER


class Refs:
    heads: Mapping[str,CommitRef]
    tags: Mapping[str,Tag]
    remotes: Mapping[str,Remote]

    def __init__(self, root_mapper, serializer):
        serializer = SERIALIZERS[serializer]
        self.heads = serializer.get_mapper(SubfolderMapper("heads", root_mapper))
        self.tags = serializer.get_mapper(SubfolderMapper("tags", root_mapper))
        self.remotes = serializer.get_mapper(SubfolderMapper("remotes", root_mapper))

    def update(self, other):
        self.heads.update(other.heads)
        self.tags.update(other.tags)