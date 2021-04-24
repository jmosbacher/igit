
import param
import treelib
from .trees import BaseTree

class TreeView(param.Parameterized):
    _tree = param.ClassSelector(BaseTree)
    _view = None

    @property
    def view(self):
        if self._view is None:
            self._view = self.panel()

    def panel(self):
        pass
