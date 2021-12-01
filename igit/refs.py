from typing import Mapping

from .models import CommitRef, Tag
from .remotes import Remote


class Refs:
    heads: Mapping[str, CommitRef]
    tags: Mapping[str, Tag]
    remotes: Mapping[str, Remote]

    def __init__(self, heads, tags=None, remotes=None):
        self.heads = heads
        if tags is None:
            tags = {}
        self.tags = tags

        if remotes is None:
            remotes = {}
        self.remotes = remotes

    def update(self, other):
        self.heads.update(other.heads)
        self.tags.update(other.tags)

    def __getitem__(self, key):
        if key in self.heads:
            return self.heads[key]
        if key in self.tags:
            return self.tags[key]
        raise KeyError(key)

    def __contains__(self, key):
        if key in self.heads:
            return True
        if key in self.tags:
            return True
        return False
