
import fsspec
from collections.abc import Mapping
import pathlib
import time
import os

# from .object_store import ObjectStore
from .refs import Refs
from .trees import collect_intervals, BaseTree
from .models import TreeRef, RepoIndex, User
from .igit import IGit
from .storage import SubfolderMapper, IGitObjectStore, ObjectStorage, BinaryStorage
from .utils import ls
from .visualizations import echarts_graph, get_pipeline_dag
from .config import Config
from .encryption import ENCRYPTORS
from .constants import CONFIG_NAME

class Repo:
    fstore: Mapping 
    igit: IGit

    def __init__(self, config, key=None, **kwargs):
        if isinstance(config,  pathlib.Path):
            config = str(config)
        if isinstance(config, str):
            config = os.path.join(config, CONFIG_NAME)
            with fsspec.open(config, "rb") as f:
                config = Config.parse_raw(f.read())
        if not isinstance(config, Config):
            raise TypeError("config must be a valid path or Config object")

        repo = fsspec.get_mapper(config.root_path, **kwargs)
        
        encryptor_class = ENCRYPTORS.get(config.encryption, None)
        if encryptor_class is not None and key is not None:
            encryptor = encryptor_class(key)
        else:
            encryptor = None

        igit_folder = SubfolderMapper(config.igit_path, repo)

        working_tree = None

        objects_store = BinaryStorage(igit_folder, 
                     compressor=config.compression,
                     encryptor=encryptor)
        objects = IGitObjectStore(d=objects_store,
                                 serializer=config.serializer,
                                 hash_func=config.hash_func)
        refs = Refs(SubfolderMapper(config.refs_path, repo))
        igit = IGit(working_tree=working_tree, config=config,
                    index=None, objects=objects, refs=refs)
        self.igit = igit
        self.fstore = repo
        self.ostore = ObjectStorage(d=repo,
                        serializer=config.serializer,)
        self.load()

    @classmethod
    def init(cls, path, bare=False, main_branch="master",
             username=None, email=None, connection_kwargs={}, **kwargs):
        if isinstance(path,  pathlib.Path):
            path = "file://" + str(path)
        if isinstance(path, str):
            repo = fsspec.get_mapper(path)
        else:
            repo = path
            protocol = repo.fs.protocol
            if isinstance(protocol, tuple):
                protocol = protocol[0]
            if protocol == "ssh":
                path = f"ssh://{repo.host}:{repo.root}"
            else:
                path = protocol + "://" + repo.root
        if not isinstance(repo, fsspec.mapping.FSMap):
            raise TypeError("repo must be a valid fsspec path or FSMap")
        
        if CONFIG_NAME in repo:
            raise ValueError(f"igit repository already exists in path.")

        kwargs = dict(kwargs)
        key = kwargs.pop("key", None)

        user = User.get_user(username=username, email=email)
        config = Config(HEAD=main_branch, main_branch=main_branch,
                         user=user, root_path=path, **kwargs)
        repo[CONFIG_NAME] = config.json(indent=3).encode()
        
        return cls(config, key=key, connection_kwargs=connection_kwargs)

    @classmethod
    def clone(cls, source, target=None, branch="master", **kwargs):
        if target is None:
            target = "file://" + source.rpartition("/")[-1]
        repo = cls.init(target, **kwargs)
        source = cls(source)
        head = source.igit.refs.heads[branch]
        for obj in head.walk(source.igit.objects):
            repo.igit.objects.hash_object(obj)

        # for k,v in source.igit.objects.items():
        #     repo.igit.objects[k] = v

        repo.igit.refs.heads[branch] = head
        repo.igit.config = source.igit.config
        repo.igit.config.root_path = target
        repo.igit.config.HEAD = branch
        repo.igit.checkout(branch)
        return repo

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
        
        protocol = self.fstore.fs.protocol
        if isinstance(protocol, tuple):
            protocol = protocol[-1]
        if protocol in ["ssh", "sftp"]:
            uri = f"{protocol}://{self.fstore.fs.host}:{self.fstore.root}"
        else:
            uri = protocol + "://" + self.fstore.root
            # uri = path #self.fstore.fs.protocol+"://"+self.path
        
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
        import igit
        app = igit.server.make_app(self.location)
        uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")

    def save(self):
        self.ostore["working_tree"] = self.igit.WORKING_TREE
        self.fstore[CONFIG_NAME] = self.igit.config.json(indent=3).encode()
      
    def load(self):
        tree = self.ostore.get("working_tree", None)
        if tree is not None:
            self.igit.working_tree = tree
        self.igit.config = Config.parse_raw(self.fstore[CONFIG_NAME])

    def new_group(self, kind):
        pass

    def _repr_mimebundle_(self, include=None, exclude=None):
        try:
            import panel as pn
            from .hashing import NumpyJSONEncoder
            import json
            d = self.to_nested_label_dict()
            data = json.dumps(d, cls=NumpyJSONEncoder)
            p = pn.pane.JSON(data,depth=3, theme="light", sizing_mode="stretch_both")
            return p._repr_mimebundle_(include=include, exclude=exclude)
        except:
            return repr(self)

    def echarts_tree(self):
        branch = self.igit.branch()
        if self.dirty:
            branch = "*"+branch
        return self.igit.working_tree.echarts_tree(f"Working tree: {branch}")
 
    def explore(self):
        from .visualizations import TreeExplorer
        label = self.igit.branch() or "root"
        return self.igit.working_tree.explorer(label).panel()

    def ls(self):
        return ls(self.fstore)

    def show_heritage(self):
        import panel as pn
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
        sel = FileSelector()

        protocol = self.fstore.fs.protocol
        if isinstance(protocol, tuple):
            protocol = protocol[-1]
        sel.protocol.value = sel.prev_protocol = protocol
        sel._fs = self.fstore.fs
        sel.url.value = self.fstore.root
        sel.go_clicked()
        return sel
