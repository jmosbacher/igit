from typing import Mapping

from .models import CommitRef, Tag
from .storage import SubfolderMapper, IGitModelStorage
from .remotes import Remote

class Refs:
    heads: Mapping[str,CommitRef]
    tags: Mapping[str,Tag]
    remotes: Mapping[str,Remote]

    def __init__(self, root_mapper):
        self.heads = SubfolderMapper("heads", IGitModelStorage(CommitRef, root_mapper))
        self.tags = SubfolderMapper("tags", IGitModelStorage(Tag, root_mapper))
        self.remotes = SubfolderMapper("remotes", IGitModelStorage(Remote, root_mapper))

    def update(self, other):
        self.heads.update(other.heads)
        self.tags.update(other.tags)