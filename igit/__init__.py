"""Top-level package for igit."""

__author__ = """Yossi Mosbacher"""
__email__ = 'joe.mosbacher@gmail.com'
__version__ = '0.1.1'

from .irepo import IRepo
from .utils import *
from . import server, interval_utils, storage
from .trees import *

def init(path, **kwargs):
    return IRepo.init(path, **kwargs)
