from collections.abc import MutableMapping

from zict import Func

from .common import ProxyStorage


class FunctionStorage(Func, ProxyStorage):
    def __init__(self, d, dump, load):
        super().__init__(dump, load, d)
