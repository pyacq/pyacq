# coding: utf8
 
from .version import version as __version__
from .core import *
import logging

logging.basicConfig(format='[%(process)s] %(message)s')
