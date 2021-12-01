from .base import BaseObject
from .reference import TreeRef
from .user import User


class RepoIndex(BaseObject):
    working_tree: TreeRef
    last_save: int
    user: User = None
