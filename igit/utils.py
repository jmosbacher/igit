from .objects import Interval


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
