
from collections import defaultdict

from .base import BaseTree
from .labels import LabelGroup
from .intervals import IntervalGroup, Interval, IntervalTree
from ..interval_utils import interval_dict_to_df


@BaseTree.register_tree_class
class ConfigGroup(LabelGroup):

    def __setitem__(self, key, value):
        if isinstance(value, BaseTree) and not isinstance(value, IntervalGroup):
            raise TypeError("Config subgroups can only be of type IntervalGroup")
        super().__setitem__(key, value)

    @staticmethod
    def mergable(name,ivs,begin,end):
        return [Interval(max(iv.begin, begin), min(iv.end, end), (name, iv.data)) for iv in ivs]
    
    def boundaries(self, begin, end, *keys):
        if not keys:
            keys = self._mapping.keys()
        merged = []
        for k in keys:
            v = self._mapping[k]
            if isinstance(v, IntervalGroup):
                ivs = v.overlap(begin, end)
            else:
                ivs = [Interval(begin, end, v)]
            merged.extend(self.mergable(k, ivs, begin, end))
        tree = IntervalTree(merged)
        tree.split_overlaps()
        cfg = {k:[] for k in keys}
        for iv in tree:
            cfg[iv.data[0]].append(Interval(iv.begin, iv.end, iv.data[1]))
        cfg = {k: sorted(v) for k,v in cfg.items()}
        return cfg

    def boundaries_df(self, begin, end, *keys):
        return interval_dict_to_df(self.boundaries(begin, end, *keys))

    def split_on_boundaries(self, begin, end, *keys):
        config = defaultdict(dict)
        cfg = self.boundaries(begin, end, *keys)
        for k, ivs in cfg.items():
            for iv in ivs:
                config[(iv.begin, iv.end,)][k] = iv.data
        return dict(config)

    def show_boundaries(self, begin, end, *keys, show_labels=True,  **kwargs):
        import holoviews as hv
        import panel as pn
        pn.extension()
        df = self.boundaries_df(begin, end, *keys)
        df["value_str"] = df.value.apply(lambda x: str(x))
        

        opts = dict(color="value_str", responsive=True, cmap="Category20", title="Interval boundaries",
         height=len(df["parameter"].unique())*30+80, line_width=30, alpha=0.5, tools=['hover'])
        opts.update(**kwargs)
        segments = hv.Segments(df, ["begin","parameter","end", "parameter"], ['value_str']).opts(**opts)
        
        vline = hv.Overlay([hv.VLine(x).opts(color="grey", line_width=1) for x in df.end.unique()])
        range_view = segments
        if show_labels:
            df["label"] = df.value.apply(lambda x: str(x)[:8])
            labels = hv.Labels(df, ["mid", "parameter"], ["label", 'value_str'])
            range_view = range_view*labels
        range_view = range_view*vline

        range_selection = hv.Segments((begin-0.1*(end-begin), 'view', end+0.1*(end-begin), 'view', 'full range'), ["begin","parameter","end", "parameter"], )
        range_selection.opts(height=100, yaxis=None, default_tools=[], responsive=True,)

        hv.plotting.links.RangeToolLink(range_selection, segments)
        layout = (range_view+range_selection).cols(1)
        layout = layout.opts(hv.opts.Layout(shared_axes=False, merge_tools=False))
        return pn.Column(layout, sizing_mode="stretch_both")
