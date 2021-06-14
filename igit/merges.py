from .models import Commit
from .diffs import Diff

class MergeStrategy:
    source: Commit
    target: Commit
    

    def apply(self, db):
        raise NotImplementedError

class AutoMerge(MergeStrategy):
    
    def apply(self, db):
        common = find_common_ancestor(db, self.source, self.target).deref_tree(db)
        sdiff = common.diff(self.source.deref_tree(db))
        tdiff = common.diff(self.target.deref_tree(db))