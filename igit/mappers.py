from zict.common import ZictBase, close


class SubfolderMapper(ZictBase):
    name: str
    sep: str

    def __init__(self, name, d, sep="/"):
        self.name = name
        self.d = d
        self.sep = sep

    @property
    def prefix(self):
        return  self.name + self.sep

    def long_key(self, key):
        if not key.startswith(self.prefix):
            key = (self.prefix + key.lstrip(self.sep)).lstrip(self.sep)
        return key

    def short_key(self, key):
        if key.startswith(self.prefix):
            key = key[len(self.prefix):]
        return key

    def __getitem__(self, key):
        key = self.long_key(key)
        return self.d[key]

    def __setitem__(self, key, value):
        key = self.long_key(key)
        self.d[key] = value

    def __contains__(self, key):
        key = self.long_key(key)
        return key in self.d

    def __delitem__(self, key):
        key = self.long_key(key)
        del self.d[key]

    def keys(self):
        return [self.short_key(k) for k in self.d.keys() if k.startswith(self.prefix) and k]

    def values(self):
        return (v for k,v in self.d.items() if k.startswith(self.prefix) and k)

    def items(self):
        return ((self.short_key(k),self.d[k]) for k in self.d.keys() if k.startswith(self.prefix) and k)

    def _do_update(self, items):
        self.d.update((self.long_key(k), v) for k, v in items if k)

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __str__(self):
        return "<Subfolder: %s%s -> %s>" % (
            self.sep,
            self.name,
            str(self.d),
        )

    __repr__ = __str__

    def flush(self):
        self.d.flush()

    def close(self):
        close(self.d)

class ObjectStoreMapper(SubfolderMapper):
    n: int
    sep: str
    prefix = ""

    def __init__(self, d, n=2, sep="/"):
        self.d = d
        self.n = n
        self.sep = sep
        

    def long_key(self, key):
        return self.sep.join([key[:self.n], key[self.n:]])

    def short_key(self, key):
        return key[:self.n]+key[self.n+1:]

    def __str__(self):
        return "<ObjectStore: S[:%s]%sS[%s:] -> bytes>" % (
            str(self.n),
            self.sep,
            str(self.n),
            
        )

    __repr__ = __str__