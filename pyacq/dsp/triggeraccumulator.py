from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import numpy as np

from ..core import (Node, register_node_type, ThreadPollInput, StreamConverter)




class TriggerAccumulator(Node,  QtCore.QObject):
    _input_specs = {'signals' : dict(streamtype = 'signals', transfermode='sharedarray', timeaxis = 1), 
                                'events' : dict(streamtype = 'events', dtype ='int64', shape = (-1, )),
                                }
    _output_specs = {}
    
    _default_params = [
            {'name': 'left_sweep', 'type': 'float', 'value': -1., 'step': 0.1,'suffix': 's', 'siPrefix': True},
            {'name': 'right_sweep', 'type': 'float', 'value': 1., 'step': 0.1, 'suffix': 's', 'siPrefix': True},
            { 'name' : 'stack_size', 'type' :'int', 'value' : 1,  'limits':[1,np.inf] },
                ]

    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
    
    def _configure(self, max_stack_size = 10):
        self.params = pg.parametertree.Parameter.create( name='Accumulator options',
                                                    type='group', children =self._default_params)
        self.params.sigTreeStateChanged.connect(self.on_params_change)
        self.max_stack_size = max_stack_size
        self.params.param('stack_size').setLimits([1, self.max_stack_size])
        

    def after_input_connect(self, inputname):
        self.nb_channel, _ = self.inputs['signal'].params['shape']
        

    def _initialize(self):
        self.thread = self._TriggerThread(self.input, self.output)
        self.thread.change_params(self.params)
        self.new_params.connect(self.thread.change_params)
        
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def on_params_change(self):
        pass

