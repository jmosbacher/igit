from .common import ProxyStorage


class SubfolderStorage(ProxyStorage):
    name: str
    sep: str

    def __init__(self, d, name, sep="/"):
        super().__init__(d)
        self.name = name
        self.sep = sep

    @property
    def prefix(self):
        return self.name + self.sep

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
        for k in self.d.keys():
            if k and k.startswith(self.prefix):
                yield self.short_key(k)

    def values(self):
        for k, v in list(self.d.items()):
            if k and k.startswith(self.prefix):
                yield v

    def items(self):
        for k in self.d.keys():
            if k and k.startswith(self.prefix):
                yield self.short_key(k), self.d[k]

    def _do_update(self, items):
        self.d.update((self.long_key(k), v) for k, v in items if k)

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(list(self.keys()))

    def __str__(self):
        return "<Subfolder: %s%s -> %s>" % (
            self.sep,
            self.name,
            str(self.d),
        )

    __repr__ = __str__


class SubfolderByKeyStorage(SubfolderStorage):
    n: int
    sep: str
    prefix: str

    def __init__(self, d, n=2, sep="/", name=""):
        self.d = d
        self.n = n
        self.sep = sep
        self.name = name

    def long_key(self, key):
        return self.sep.join([key[:self.n], key[self.n:]])

    def short_key(self, key):
        return key[:self.n] + key[self.n + len(self.sep):]

    def __str__(self):
        return f"<SubfolderStorage: key[:{self.n}]{self.sep}key[{self.n}:] -> value>"

    __repr__ = __str__
