"""Top-level package for igit."""

__author__ = """Yossi Mosbacher"""
__email__ = 'joe.mosbacher@gmail.com'
__version__ = '0.1.1'

from . import interval_utils, server, storage
from .irepo import IRepo
from .trees import *
from .utils import *


def init(path, **kwargs):
    return IRepo.init(path, **kwargs)
