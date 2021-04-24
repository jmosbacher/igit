from pydantic import BaseModel
from typing import Any
from .models import Commit


class Change(BaseModel):
    old: Any
    new: Any

class Insertion(Change):
    old: Any = None

class Deletion(Change):
    new: Any = None

class Diff(BaseModel):
    old: Any
    new: Any
    diffs: dict

class CommitDiff(Diff):
    old: Commit
    new: Commit
    
