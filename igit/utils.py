import treelib
from .objects import Interval

def dict_to_treelib(d, parent="", tree=None):
    if tree is None:
        tree = treelib.tree.Tree()
        tree.create_node(identifier=parent)
    for k,v in d.items():
        node_id = (parent or "") + "_" + str(k).lower()
        if isinstance(v, dict):
            tree.create_node(tag=k, identifier=node_id, parent=parent)
            dict_to_treelib(v, parent=node_id, tree=tree)
        else:
            tree.create_node(tag=k, identifier=node_id, parent=parent, data=v)
    return tree

def contain(p, ostore, tree, resolve_refs=True):
    "Return all intervals that contain the point p."
    ivs = set()
    for iv in tree.at(p):
        ref = iv.data
        if ref.otype== "tree":
            t = ostore.get_object(ref.key)
            ivs.update(contain(p, ostore, t))
        else:
            if resolve_refs:
                data = ostore.get_object(ref.key)
            else:
                data = ref
            ivs.add(Interval(iv.begin, iv.end, data))
    return ivs

def overlap(begin, end, ostore, tree, resolve_refs=True):
    "Return all intervals that overlap the interval (begin, end)."
    ivs = set()
    for iv in tree.overlap(begin, end):
        ref = iv.data
        if ref.otype== "tree":
            t = ostore.get_object(ref.key)
            ivs.update(overlap(begin, end, ostore, t))
        else:
            if resolve_refs:
                data = ostore.get_object(ref.key)
            else:
                data = ref
            ivs.add(Interval(iv.begin, iv.end, data))
    return ivs

def nested_diff(a,b):
    c = copy(a)
    c.update(b)
    for k in (a.keys() & b.keys()):
        if isinstance(a[k], dict) and isinstance(b[k], dict):
            diff = nested_diff(a[k], b[k])
            if len(diff):
                c[k] = diff
            else:
                del c[k]
        elif a[k]==b[k]:
            del c[k]
        else:
            c[k] = (a[k], b[k])
    return c

