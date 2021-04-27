
import fsspec
from collections.abc import Mapping
import pathlib
import time

# from .object_store import ObjectStore
from .refs import Refs
from .trees import collect_intervals, BaseTree
from .models import TreeRef, RepoIndex, User
from .igit import IGit
from .serializers import SERIALIZERS
from .mappers import SubfolderMapper, ObjectStoreMapper
from .utils import ls
from .visualizations import echarts_graph, get_pipeline_dag
from .config import Config
from .settings import *

class Repo:
    fstore: Mapping 
    igit: IGit

    @classmethod
    def init(cls, repo, main_branch="master", username=None, email=None):
        if isinstance(repo, (str, pathlib.Path)):
            repo = fsspec.get_mapper(repo)
        elif isinstance(repo, Mapping):
            m = fsspec.get_mapper(f"memory://igit")
            for k,v in repo.items():
                m[k] = v
            repo = m
        else:
            raise TypeError("repo must be a valid path or Mapping")
        if IGIT_PATH in repo:
            raise ValueError(f"igit repository already exists.")
        user = User.get_user(username=username, email=email)
        config = Config(HEAD=main_branch, user=user)
        repo[CONFIG_PATH] = config.json().encode()
        return cls(repo, config=config)

    @classmethod
    def remote(cls, url, branch="master", **kwargs):
        repo = cls.init(repo=url, **kwargs)
        repo.igit.checkout(branch)
        return repo

    @classmethod
    def clone(cls, other, repo, branch="master", **kwargs):
        repo = cls.init(repo, **kwargs)
        kwargs = dict(**kwargs)
        other = cls(repo=other, **kwargs)
        repo.igit.objects.update(other.igit.objects)
        repo.igit.refs.update(other.igit.refs)
        repo.igit.config = other.igit.config
        repo.igit.checkout(branch)
        return repo

    def __init__(self, repo, **kwargs):
        if isinstance(repo, (str, pathlib.Path)):
            repo = fsspec.get_mapper(repo)
        elif isinstance(repo, Mapping):
            pass
        else:
            raise TypeError("repo must be a valid path or Mapping")

        if CONFIG_PATH not in repo:
            raise ValueError(f"{repo} is not a valid igit repository.")

        serializer = kwargs.pop("serializer", DEFAULT_SERIALIZER)
        config = kwargs.pop("config", None)
        index = kwargs.pop("index", None)
        working_tree = kwargs

        # igit_mapper = SubfolderMapper(IGIT_PATH, repo)
        objects = ObjectStoreMapper(SubfolderMapper(DB_PATH, repo))
        refs = Refs(SubfolderMapper(REFS_PATH, repo), serializer=serializer)
        igit = IGit(working_tree=working_tree, config=config,
                    index=index, objects=objects, refs=refs, serializer=serializer)
        self.igit = igit
        self.fstore = repo
        self.load()

    def __getitem__(self, key):
        return self.igit.working_tree[key]
        
    def __setitem__(self, key, value):
        self.igit.working_tree[key] = value

    def __getattr__(self, key):
        return getattr(self.igit.working_tree, key)

    def __delitem__(self, key):
        if key in self.igit.working_tree:
            del self.igit.working_tree[key]
        raise KeyError(key)

    def __dir__(self):
        create_methods = [k for k in dir(self.igit.working_tree) if k.startswith("new")]
        tree_values =  list(self.igit.working_tree.keys())
        return create_methods + tree_values + super().__dir__()

    def __repr__(self):
        return self.show_tree(stdout=False)

    @property
    def path(self):
        if isinstance(self.fstore, fsspec.FSMap):
            return self.fstore.root
        return ""

    @property
    def uri(self):
        if isinstance(self.fstore, fsspec.FSMap):
            uri = self.fstore.fs.protocol+"://"+self.path
        else:
            uri = self.path
        return uri

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
        app = igit.server.make_app(self.location)
        uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")

    def save(self):
        keys = list(self.fstore.keys())
        for k in keys:
            if k.startswith(IGIT_PATH):
                continue
            del self.fstore[k]
            
        ref = self.igit.working_tree.hash_tree(self.fstore)
        index = RepoIndex(working_tree=ref, last_save=int(time.time()))
        self.fstore[CONFIG_PATH] = self.igit.config.json().encode()
        self.fstore[INDEX_PATH] = index.json().encode()
        return ref

    def load(self):
        try:
            index = self.fstore[INDEX_PATH]
            index = RepoIndex.parse_raw(index)
            self.igit.working_tree = index.working_tree.deref(self.fstore)
            self.igit.config = Config.parse_raw(self.fstore[CONFIG_PATH])
        except:
            pass
        return self

    def new_group(self, kind):
        pass

    def __iter__(self):
        pass

    def __len__(self):
        pass

    def compatible_keys(self, keys):
        pass
    
    def from_dict(self, d):
        pass

    def from_label_dict(self, d):
        pass

    def symmetric_difference(self, other):
        pass

    def to_dict(self):
        pass

    def to_label_dict(self):
        pass

    def _repr_mimebundle_(self, include=None, exclude=None):
        try:
            import panel as pn
        except:
            return repr(self)
        d = self.to_nested_label_dict()
        p = pn.pane.JSON(d,depth=3, theme="light", sizing_mode="stretch_both")
        return p._repr_mimebundle_(include=include, exclude=exclude)

    def echarts_tree(self):
        branch = self.igit.branch()
        if self.dirty:
            branch = "*"+branch
        return self.igit.working_tree.echarts_tree(f"Working tree: {branch}")
        # import panel as pn
        # pn.extension('echarts')
        # 
        # echart = echarts_graph(self.igit.working_tree.to_echarts_series("root"), f"Working tree: {branch}")
        # echart_pane = pn.pane.ECharts(echart, width=700, height=400, sizing_mode="stretch_both")
        # return echart_pane

    def explore(self):
        from .visualizations import TreeExplorer
        label = self.igit.branch() or "root"
        return self.igit.working_tree.explorer(label).panel()

    def ls(self):
        return ls(self.fstore)

    def show_heritage(self):
        if self.igit.HEAD is None:
            return pn.Column()
        return self.igit.HEAD.visualize_heritage(self.igit.objects)

    def browse_history(self):

        if self.igit.HEAD is None:
            import panel as pn
            return pn.Column()
        pipeline, dag = get_pipeline_dag(self.igit.HEAD, self.igit.objects)
        pipeline.define_graph(dag)
        return pipeline


    def browse_files(self):
        from fsspec.gui import FileSelector
        return FileSelector(self.uri)
