# coding: utf8
 
from .version import version as __version__
from .core import *
from .devices import *
from .viewers import *

import logging

logging.basicConfig(format='[%(process)s] %(message)s')
