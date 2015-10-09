from pyqtgraph.Qt import QtCore
import pyqtgraph as pg

import numpy as np

from ..core import (Node, register_node_type, ThreadPollInput, StreamConverter)



class TriggerBase(Node):
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'signals' : dict(streamtype = 'signals')}
    
    _default_params = [
                        {'name': 'channel', 'type': 'int', 'value': 0},
                        {'name': 'threshold', 'type': 'float', 'value': 0.},
                        {'name': 'debounce_mode', 'type': 'list', 'value': 'scroll' ,
                                            'values' : ['no-debounce', 'after-stable', 'before-stable'] },
                        {'name': 'debounce_time', 'type': 'float', 'value': 0.01},
                ]
    
    def _configure(self):
        pass

    def _initialize(self):
        pass
    
    def _start(self):
        pass
    
    def _stop(self):
        pass


