
import param
import treelib
from .trees import BaseTree


def tree_labels(keys):
    if not keys:
        return []
    labels =[f"\u255f\u2500\u2500 {k}" for k in keys[:-1] if k]
    labels.append(f"\u2559\u2500\u2500 {keys[-1]}")
    return labels

def clean_label(key):
    return key.lstrip("\u255f\u2500\u2500 ").lstrip("\u2559\u2500\u2500 ")

class TreeExplorer(param.Parameterized):
    label = param.String("Tree")
    tree = param.ClassSelector(BaseTree)
    selector = param.Parameter()
    _view = None

    @property
    def view(self):
        if self._view is None:
            self._view = self.panel()
        return self._view


class LabelTreeExplorer(TreeExplorer):
    label = param.String("Tree")
    tree = param.ClassSelector(BaseTree)
    selector = param.Parameter()
    _view = None

    @property
    def view(self):
        if self._view is None:
            self._view = self.panel()
        return self._view

    def panel(self):
        import panel as pn
        top = pn.Row(self._menu_view(), pn.Column(f"### {self.label} selection:",self._leaf_view))
        return pn.Column(top, self._tree_view, sizing_mode="stretch_both")

    @param.depends("tree")
    def _menu_view(self):
        import panel as pn

        d = self.tree.to_label_dict()
        labels = tree_labels(list(d.keys()))
        options = dict(zip(labels, d.values()))
        multi_select = pn.widgets.MultiSelect(name=self.label, value=[],
            options=options, size=8)
        self.selector = multi_select
        return multi_select

    @param.depends("selector.value")
    def _tree_view(self):
        import panel as pn
        if not self.selector.value:
            return pn.Column()
        selected = self.selector.value[0]
        for label, v in self.selector.options.items():
            if v == selected:
                break
        label = clean_label(label)
        if isinstance(selected, BaseTree):
            return pn.panel(selected.explorer(title=label).panel())
        return pn.Column()

    @param.depends("selector.value")
    def _leaf_view(self):
        import panel as pn
        if not self.selector.value:
            return pn.Column()
        selected = self.selector.value[0]
        for label, v in self.selector.options.items():
            if v == selected:
                break
        label = clean_label(label)
        if isinstance(selected, BaseTree):
            return pn.Column()
        
        if isinstance(selected, (int, float)):
            return self._number_view(label, selected)
        return self._text_view(label, selected)

    def _number_view(self, k, v):
        import panel as pn
        return pn.indicators.Number(name=k, value=v, font_size="35pt", title_size="15pt",
                     format="{value}", sizing_mode="stretch_both")

    def _text_view(self, k, v):
        import panel as pn
        return pn.Column(f"## {k}",  f"{v}")


class IntervalTreeExplorer(TreeExplorer):
    keys = param.List()
    values = param.List()
    _tree_view = param.Parameter()

    def panel(self):
        import panel as pn
        iview = self._interval_view()
        return pn.Column(iview, self.tree_view, 
            sizing_mode="stretch_both")

    @param.depends("tree")
    def _interval_view(self):
        import panel as pn
        import holoviews as hv
        hv.extension("bokeh")
        df = self.tree.to_df(self.label)
        self.keys = list(self.tree.keys())
        # self.values = list(self.tree.values())
        plot = hv.Segments(df, kdims=["begin", "parameter",  "end", "parameter"], vdims="data", )
        
        defaults = dict(color="data", 
                        line_width=30, alpha=0.5,
                        responsive=True,
                        height=120,
                        colorbar=True,
                        toolbar="above",
                        tools=["hover", "tap"],
                        xlabel="index",
                        nonselection_alpha=0.2,
                        nonselection_color="grey",
                        title=self.label)
        # defaults.update(opts)
        self.segments = segments = plot.opts(**defaults)
        labels = hv.Labels(df, kdims=["mid", "parameter"], vdims="label")
        plot = labels*segments
        self.selector = hv.streams.Selection1D(source=plot)
        self.selector.param.watch(self.make_tree_view, ['index'], onlychanged=True)
        self.make_tree_view()
        return pn.Column(plot, sizing_mode="stretch_width", width=700)

    @param.depends("_tree_view")
    def tree_view(self):
        import panel as pn
        if self._tree_view is None:
            return pn.Column()
        return self._tree_view

    def make_tree_view(self, *events):
        import holoviews as hv
        import panel as pn
        if not self.selector:
            self._tree_view = pn.Column("No selector")
        if not hasattr(self.selector, "index"):
            self._tree_view = pn.Column("No index")
            return
        index = self.selector.index
        if not index or not len(self.keys)>index[0]:
            self._tree_view = pn.Column("no index length or keys")
            return

        k =  self.keys[index[0]]
        v = self.tree.get(k, None)
        if isinstance(v, BaseTree):
            self._tree_view = pn.Column(v.explorer(title=str(k)).panel())
            return 
        self._tree_view = pn.Column(f"{v}")
        return 

class CommitViewer(param.Parameterized):
    db = param.Parameter()
    commit = param.Parameter()
    _tree_view = param.Parameter()

    def commit_view(self):
        import panel as pn
        c = self.commit.deref(self.db)
        return pn.Column(
                         pn.pane.JSON(c.json(), name='JSON', theme="light",
                         sizing_mode="stretch_both", height=150),
                         sizing_mode="stretch_both")
    
    @param.depends("_tree_view")
    def tree_view(self):
        import panel as pn
        if self._tree_view is not None:
            return self._tree_view
        button = pn.widgets.Button(name="Load tree", height=150)
        button.on_click(self.load_tree)
        return pn.Column(button, sizing_mode="stretch_both")
    
    def load_tree(self, *event):
        self._tree_view =  self.commit.deref_tree(self.db).echarts_tree(f"Commit: {self.commit.key[:8]}")
    
    def panel(self):
        import panel as pn
        return pn.Row(self.commit_view(), self.tree_view, sizing_mode="stretch_both")

def get_pipeline_dag(cref, db, pipeline=None, dag={}, n=6):
    if pipeline is None:
        import panel as pn
        pipeline = pn.pipeline.Pipeline(debug=True, inherit_params=False)
    c = cref.deref(db)
    cid = cref.key[:n]
    pipeline.add_stage(cid, CommitViewer(commit=cref, db=db,))
    dag[cid] = tuple(p.key[:n] for p in c.parents)
    [get_pipeline_dag(p, db, pipeline, dag=dag, n=n) for p in c.parents]
    return pipeline, dag

def echarts_graph(data, title="Tree graph"):
    
    series = [
        {
            'type': 'tree',

            'name': 'tree1',

            'data': [data],

            'top': '5%',
            'left': '7%',
            'bottom': '2%',
            'right': '60%',

            'symbolSize': 7,

            'label': {
                'position': 'left',
                'verticalAlign': 'middle',
                'align': 'right'
            },

            'leaves': {
                'label': {
                    'position': 'right',
                    'verticalAlign': 'middle',
                    'align': 'left'
                }
            },

            'emphasis': {
                'focus': 'descendant'
            },

            'expandAndCollapse': True,

            'animationDuration': 550,
            'animationDurationUpdate': 750

        },
        ]

    echart = {
        'title': {
            'text': title,
        },
            'tooltip': {
            'trigger': 'item',
            'triggerOn': 'mousemove'
        },
        'legend': {
            'top': '2%',
            'left': '3%',
            'orient': 'vertical',
            'data': [{
                'name': 'master',
                'icon': 'rectangle'
            },
            {
                'name': 'tree2',
                'icon': 'rectangle'
            }],
            'borderColor': '#c23531'
        },'tooltip': {},
        'legend': {
            'data':[]
        },
    
        'series': series,
        }
    return echart