
import treelib
import numpy as np
import networkx as nx
from collections import Counter
from intervaltree import Interval
from itertools import cycle, islice
from cryptography.fernet import Fernet
from copy import copy
import random

def dict_to_treelib(d, parent="", tree=None, show_value=True, max_tag_len=50, include_trees=False):
    if tree is None:
        tree = treelib.tree.Tree()
        tree.create_node(identifier=parent)
    for k,v in d.items():
        node_id = (parent + "_" + str(k).lower()).strip("_")
        tag = str(k)
        if isinstance(v, dict):
            data = None
            if include_trees:
                data = {k:v for k,v in v.items() if not isinstance(v, dict)}
            tree.create_node(tag=tag, identifier=node_id, parent=parent, data=data)
            dict_to_treelib(v, parent=node_id, tree=tree, show_value=show_value, include_trees=include_trees)
        else:
            if show_value:
                tag += f": {v}"
                if len(tag)>max_tag_len:
                    tag = tag[:max_tag_len] + "..."
            tree.create_node(tag=tag, identifier=node_id, parent=parent, data=v)
    return tree

def contain(p, ostore, tree, dereference=True):
    "Return all intervals that contain the point p."
    ivs = set()
    for iv in tree.at(p):
        ref = iv.data
        if ref.otype== "tree":
            t = ostore.get_object(ref.key)
            ivs.update(contain(p, ostore, t))
        else:
            if dereference:
                data = ostore.get_object(ref.key)
            else:
                data = ref
            ivs.add(Interval(iv.begin, iv.end, data))
    return ivs

def overlap(begin, end, ostore, tree, dereference=True):
    "Return all intervals that overlap the interval (begin, end)."
    ivs = set()
    for iv in tree.overlap(begin, end):
        ref = iv.data
        if ref.otype== "tree":
            t = ostore.get_object(ref.key)
            ivs.update(overlap(begin, end, ostore, t))
        else:
            if dereference:
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

def min_ch(mapper, mn=4):
    for l in range(mn, 41):
        keys = list([key[:l] for key in mapper.keys()])
        if len(set(keys)) == len(keys):
            break
    return l

def ls(mapper):
    mx = min_ch(mapper)
    return [k[:mx] for k in mapper.keys()]


def roundrobin(*iterables):
    "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
    # Recipe credited to George Sakkis
    num_active = len(iterables)
    nexts = cycle(iter(it).__next__ for it in iterables)
    while num_active:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            # Remove the iterator we just exhausted from the cycle.
            num_active -= 1
            nexts = cycle(islice(nexts, num_active))
 
def write_digraph_svg(dg, path):
    graph = nx.drawing.nx_pydot.to_pydot(dg)
    graph.write_svg(path)
    
def hierarchy_pos(G, root=None, width=1., vert_gap = 0.2, vert_loc = 0, xcenter = 0.5):
    
    '''
    From Joel's answer at https://stackoverflow.com/a/29597209/2966723.  
    Licensed under Creative Commons Attribution-Share Alike 
    
    If the graph is a tree this will return the positions to plot this in a 
    hierarchical layout.
    
    G: the graph (must be a tree)
    
    root: the root node of current branch 
    - if the tree is directed and this is not given, 
      the root will be found and used
    - if the tree is directed and this is given, then 
      the positions will be just for the descendants of this node.
    - if the tree is undirected and not given, 
      then a random choice will be used.
    
    width: horizontal space allocated for this branch - avoids overlap with other branches
    
    vert_gap: gap between levels of hierarchy
    
    vert_loc: vertical location of root
    
    xcenter: horizontal location of root
    '''
    if not nx.is_tree(G):
        raise TypeError('cannot use hierarchy_pos on a graph that is not a tree')

    if root is None:
        if isinstance(G, nx.DiGraph):
            root = next(iter(nx.topological_sort(G)))  #allows back compatibility with nx version 1.11
        else:
            root = random.choice(list(G.nodes))

    def _hierarchy_pos(G, root, width=1., vert_gap = 0.2, vert_loc = 0, xcenter = 0.5, pos = None, parent = None):
        '''
        see hierarchy_pos docstring for most arguments

        pos: a dict saying where all nodes go if they have been assigned
        parent: parent of this branch. - only affects it if non-directed

        '''
    
        if pos is None:
            pos = {root:(xcenter,vert_loc)}
        else:
            pos[root] = (xcenter, vert_loc)
        children = list(G.neighbors(root))
        if not isinstance(G, nx.DiGraph) and parent is not None:
            children.remove(parent)  
        if len(children)!=0:
            dx = width/len(children) 
            nextx = xcenter - width/2 - dx/2
            for child in children:
                nextx += dx
                pos = _hierarchy_pos(G,child, width = dx, vert_gap = vert_gap, 
                                    vert_loc = vert_loc-vert_gap, xcenter=nextx,
                                    pos=pos, parent = root)
        return pos

            
    return _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter)


def generate_key():
    return Fernet.generate_key()

def assign_branches(dag):
    
    def ndecendents(key):
        sum([ndecendents(s) for s in dag.successors(key) if s])
        
    def assign_branch(key, branch, branches):
        if key in branches:
            return branch - 1
        branches[key] = branch
        for i,skey in enumerate(dag.successors(key)):
            branch = assign_branch(skey, branch+i, branches)
        return branch
    
    branch = 0
    branches = {}
    for k in nx.topological_sort(dag):
        branch = assign_branch(k, branch, branches)
    return branches

def equal(a,b):
    if a.__class__.__name__ != b.__class__.__name__:
        return False
    if isinstance(a, list):
        return [equal(ai,bi) for ai,bi in zip(a,b)]
    if isinstance(a, dict):
        return {k: equal(a[k],b[k]) for k in a}

    try:
        ar, br = a.__reduce__(), b.__reduce__()
        if isinstance(ar, str):
            return ar == br
        else:
            return ar[1] == br[1]
    except:
        pass
    if isinstance(a, np.ndarray):
        return np.all(np.equal(a, b))
    return a == b