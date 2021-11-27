
from .function import FunctionStorage

class PydanticModelStorage(FunctionStorage):
    def __init__(self, d, model):
        dump = lambda m: m.json().encode()
        load = lambda data: model.parse_raw(data)
        super().__init__(d, dump, load)

