from typing import ClassVar, Dict

from .base import BaseObject
from .reference import ObjectRef
class BaseTree(BaseObject):
    otype: ClassVar = "tree"
    tree_type: str
    merkle_tree: Dict[str,ObjectRef]