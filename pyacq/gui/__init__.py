# -*- coding: utf-8 -*-
 
import pyqtgraph.functions
import sys
if sys.platform.startswith('win'):
    pyqtgraph.functions.USE_WEAVE = False
 
from oscilloscope import Oscilloscope
from timefreq import TimeFreq

from topoplot import Topoplot
