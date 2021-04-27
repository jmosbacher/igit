
from .base import BaseObject
from .user import User
from .reference import TreeRef


class RepoIndex(BaseObject):
    working_tree: TreeRef
    last_save: int
    user: User = None