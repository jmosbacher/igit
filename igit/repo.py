

from .object_store import ObjectStore
from .refs import Refs
from .trees import collect_intervals
from .igit import IGit
from .encoders import DEFAULT_ENCODER

class Repo:
    igit: IGit

    @classmethod
    def init(cls):
        working_tree = {}
        head = "master"
        branches = {}
        index = None
        objects = ObjectStore()
        refs = Refs()
        encoder = DEFAULT_ENCODER
        igit = IGit(working_tree=working_tree, head=head, branches=branches,
                    index=index, objects=objects, refs=refs, encoder=encoder)
        return cls(igit)

    def __init__(self, igit: IGit):
        self.igit = igit

    def __getitem__(self, key):
        return self.igit.working_tree[key]
        
    def __setitem__(self, key, value):
        self.igit.working_tree[key] = value

    def __getattr__(self, key):
        return getattr(self.igit.working_tree, key)

    def __dir__(self):
        return super().__dir__() + dir(self.igit.working_tree)

    def __repr__(self):
        return self.show_tree(stdout=False)

    @property
    def dirty(self):
        return self.igit.has_unstaged_changes

    def show_tree(self, **kwargs):
        title = self.igit.branch()
        if self.dirty:
            title = "*"+title
        return self.igit.working_tree.to_treelib(parent=title).show(**kwargs)

    def show_intervals(self, **opts):
        import panel as pn
        import holoviews as hv
        import pandas as pd
        pn.extension()
        df = pd.DataFrame(collect_intervals(self.igit.working_tree))
        plot = hv.Segments(df, kdims=["begin", "label",  "end", "label"], vdims="data", )
        title = self.igit.branch()
        if self.dirty:
            title = "*"+title
        defaults = dict(color="data", 
                        line_width=30, alpha=0.5,
                        responsive=True,
                        height=len(df.label.unique())*30+80,
                        colorbar=True,
                        toolbar="above",
                        tools=["hover"],
                        xlabel="index",
                        title=title)
        defaults.update(opts)
        segments = plot.opts(**defaults)
        labels = hv.Labels(df.dropna(), kdims=["mid", "label"], vdims="data")
        return pn.panel(segments*labels)

