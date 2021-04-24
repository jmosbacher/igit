
import fsspec
from collections.abc import Mapping
import pathlib

# from .object_store import ObjectStore
from .refs import Refs
from .trees import collect_intervals
from .igit import IGit
from .serializers import DEFAULT_SERIALIZER, SERIALIZERS
from .mappers import SubfolderMapper, ObjectStoreMapper


class Repo:
    fstore: Mapping 
    igit: IGit
    location: str

    @classmethod
    def init(cls, repo, **kwargs):
        if isinstance(repo, (str, pathlib.Path)):
            repo = fsspec.get_mapper(repo, **kwargs)

        if not isinstance(repo, Mapping):
            raise TypeError("repo must be a valid path or Mapping")

        serializer=kwargs.get("serializer", DEFAULT_SERIALIZER)
        working_tree = {}
        head = "master"
        index = None
        objects = ObjectStoreMapper(SubfolderMapper("objects", repo))
        refs = Refs(SubfolderMapper("refs", repo), serializer=serializer)
        igit = IGit(working_tree=working_tree, head=head,
                    index=index, objects=objects, refs=refs, serializer=serializer)

        
        return cls(igit, fstore=repo, location=location)

    @classmethod
    def open(cls, branch="master", **kwargs):
        repo = cls.init(repo=mapper, **kwargs)
        repo.igit.checkout(branch)
        return repo

    @classmethod
    def remote(cls, url, branch="master", **kwargs):
        repo = cls.init(repo=url, **kwargs)
        repo.igit.checkout(branch)
        return repo

    @classmethod
    def clone(cls, other, repo, branch="master", **kwargs):
        repo = cls.init(repo, **kwargs)
        kwargs = dict(**kwargs)
        other = cls.init(repo=other, **kwargs)
        repo.igit.objects.update(other.igit.objects)
        repo.igit.refs.update(other.igit.refs)
        repo.igit.checkout(branch)
        return repo

    def __init__(self, igit: IGit, fstore: Mapping, location: str=None):
        self.igit = igit
        self.fstore = fstore
        self.location = location

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
    def location(self)
        if isinstance(self.fstore, fsspec.FSMap):
            return self.fstore.root
        
    @property
    def dirty(self):
        return self.igit.has_unstaged_changes

    def show_tree(self, **kwargs):
        title = self.igit.branch()
        if self.dirty:
            title = "*"+title
        return self.igit.working_tree.to_treelib(parent=title).show(**kwargs)

    def show_intervals(self, join_char="; ", **opts):
        import panel as pn
        import holoviews as hv
        import pandas as pd
        pn.extension()
        df = pd.DataFrame(collect_intervals(self.igit.working_tree, join_char=join_char))
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

    def serve(self):
        import uvicorn
        app = igit.server.make_app(path)
        uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")
