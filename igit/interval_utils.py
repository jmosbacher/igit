from intervaltree import IntervalTree, Interval
from typing import Mapping
from collections import defaultdict

def interval_dict_to_df(d):
    import pandas as pd
    rows = []
    for p,ivs in d.items():
        for iv in ivs:
            row = {"begin": iv.begin, "mid": iv.begin+0.5*(iv.end-iv.begin),
             "end": iv.end, "parameter": p, "value": iv.data}
            rows.append(row)
    return pd.DataFrame(rows)

