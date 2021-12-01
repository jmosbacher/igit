from collections import Counter

from .diffs import Diff
from .models import Commit
from .refs import CommitRef
from .utils import roundrobin


def find_common_ancestor(repo, *branches):
    refs = []
    for branch in branches:
        if isinstance(branch, CommitRef):
            ref = branch
        elif isinstance(branch, str):
            if branch in repo.refs.heads:
                ref = repo.refs.heads[branch]
            else:
                ref = repo.get_ref(branch)
        refs.append(ref)

    keys = Counter()
    for cref in roundrobin(*[r.walk_parents(repo.objects) for r in refs]):
        keys[cref.key] += 1
        if keys[cref.key] == len(refs):
            return cref


class MergeStrategy:
    source: Commit
    target: Commit

    def apply(self, db):
        raise NotImplementedError


class AutoMerge(MergeStrategy):
    def apply(self, db):
        common = find_common_ancestor(db, self.source,
                                      self.target).deref_tree(db)
        sdiff = common.diff(self.source.deref_tree(db))
        tdiff = common.diff(self.target.deref_tree(db))
