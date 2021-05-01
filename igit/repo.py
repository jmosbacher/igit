
import fsspec
from collections.abc import Mapping
import pathlib
import time

# from .object_store import ObjectStore
from .refs import Refs
from .trees import collect_intervals, BaseTree
from .models import TreeRef, RepoIndex, User
from .igit import IGit
from .storage import SubfolderMapper, IGitObjectStore, ObjectStorage, BinaryStorage
from .utils import ls
from .visualizations import echarts_graph, get_pipeline_dag
from .config import Config
from .settings import *

class Repo:
    fstore: Mapping 
    igit: IGit

    @classmethod
    def init(cls, repo, db=None, main_branch="master", username=None, email=None):
        if isinstance(repo, (str, pathlib.Path)):
            repo = fsspec.get_mapper(repo)
        elif isinstance(repo, Mapping):
            m = fsspec.get_mapper(f"memory://igit")
            for k,v in repo.items():
                m[k] = v
            repo = m
        else:
            raise TypeError("repo must be a valid path or Mapping")

        repo = BinaryStorage(d=repo)
        if CONFIG_PATH in repo:
            raise ValueError(f"igit repository already exists in path.")
        user = User.get_user(username=username, email=email)
        config = Config(HEAD=main_branch, user=user)
        repo[CONFIG_PATH] = config.json().encode()
        return cls(repo, db=db)

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

    def __init__(self, repo, db=None, bare=False, **kwargs):
        if isinstance(repo,  pathlib.Path):
            repo = str(repo)
        if isinstance(repo, str):
            repo = fsspec.get_mapper(repo)
        elif isinstance(repo, Mapping):
            pass
        else:
            raise TypeError("repo must be a valid path or Mapping")
        
        
        if isinstance(db, pathlib.Path):
            db = str(db)
        if isinstance(db, str):
            db = fsspec.get_mapper(db)
        elif isinstance(db, Mapping):
            pass
        elif db is None:
            db = SubfolderMapper(IGIT_PATH, repo)
        else:
            raise TypeError("db must be a valid path or Mapping")
        if CONFIG_PATH not in repo:
            raise ValueError(f"{repo} is not a valid igit repository.")

        config = Config.parse_raw(repo[CONFIG_PATH])
        index = kwargs.pop("index", None)
        if bare:
            working_tree = None
        else:
            working_tree = kwargs
        objects = IGitObjectStore(d=db)
        # ref_store = ObjectStorage(d=)
        refs = Refs(SubfolderMapper(REFS_PATH, repo))
        igit = IGit(working_tree=working_tree, config=config,
                    index=index, objects=objects, refs=refs)
        self.igit = igit
        self.fstore = repo
        self.ostore = ObjectStorage(d=repo)
        self.load()

    def __getitem__(self, key):
        return self.igit.WORKING_TREE[key]
        
    def __setitem__(self, key, value):
        self.igit.WORKING_TREE[key] = value

    def __getattr__(self, key):
        return getattr(self.igit.WORKING_TREE, key)

    def __delitem__(self, key):
        if key in self.igit.WORKING_TREE:
            del self.igit.WORKING_TREE[key]
        raise KeyError(key)

    def __dir__(self):
        create_methods = [k for k in dir(self.igit.WORKING_TREE) if k.startswith("new")]
        tree_values =  list(self.igit.WORKING_TREE.keys())
        return create_methods + tree_values + super().__dir__()

    def __repr__(self):
        return self.show_tree(stdout=False)

    @property
    def path(self):
        if hasattr(self.fstore, "root"):
            return self.fstore.root
        return ""

    @property
    def uri(self):
        if hasattr(self.fstore, "fs"):

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
        return self.igit.WORKING_TREE.to_treelib(parent=title).show(**kwargs)

    def show_intervals(self, join_char="; ", **opts):
        import panel as pn
        import holoviews as hv
        import pandas as pd
        pn.extension()
        df = pd.DataFrame(collect_intervals(self.igit.WORKING_TREE, join_char=join_char))
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
        self.ostore["working_tree"] = self.igit.WORKING_TREE
        # keys = list(self.fstore.keys())
        # for k in keys:
        #     if k.startswith(IGIT_PATH):
        #         continue
        #     del self.fstore[k]
        # ref = self.igit.working_tree.hash_tree(self.fstore)
        # index = RepoIndex(working_tree=ref, last_save=int(time.time()))
        # self.fstore[CONFIG_PATH] = self.igit.config.json().encode()
        # self.fstore[INDEX_PATH] = index.json().encode()
        # return ref

    def load(self):
        tree = self.ostore.get("working_tree", None)
        if tree is not None:
            self.igit.working_tree = tree
        # try:
        #     index = self.fstore[INDEX_PATH]
        #     index = RepoIndex.parse_raw(index)
        #     self.igit.working_tree = index.working_tree.deref(self.fstore)
        #     self.igit.config = Config.parse_raw(self.fstore[CONFIG_PATH])
        # except:
        #     pass
        # return self

    def new_group(self, kind):
        pass

    # def __iter__(self):
    #     pass

    # def __len__(self):
        # pass

    # def compatible_keys(self, keys):
    #     pass
    
    # def from_dict(self, d):
    #     pass

    # def from_label_dict(self, d):
    #     pass

    # def to_dict(self):
    #     pass

    # def to_label_dict(self):
    #     pass

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
