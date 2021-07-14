"""Top-level package for igit."""

__author__ = """Yossi Mosbacher"""
__email__ = 'joe.mosbacher@gmail.com'
__version__ = '0.1.1'

from .repo import Repo
from .utils import *
from . import server, interval_utils, storage
from .demo import demo_repo
from .trees import *