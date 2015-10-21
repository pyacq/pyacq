# coding: utf8
import faulthandler
faulthandler.enable()
 
from .version import version as __version__
from .core import *
from .devices import *
from .viewers import *

import logging

logging.basicConfig(format='[%(process)s:%(thread)x] %(message)s')
