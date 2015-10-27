from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import numpy as np


from ..core import (Node, register_node_type, ThreadPollOuput)


class ThreadPollOuputUntilPosLimit(ThreadPollOuput):
    """
    Thread waiting a futur pos in a stream.
    """
    limit_reached = QtCore.pyqtSignal()
    def __init__(self, pos, pos_limit, **kargs):
        ThreadPollOuput.__init__(self, **kargs)
        self.pos = pos
        self.pos_limit = pos_limit
    
    def process_data(self, pos, data):
        if pos>self.pos_limit:
            self.limit_reached.emit()


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
        self.sample_rate = self.inputs['signal'].params['sample_rate']
    
    
    def _initialize(self):
        self.trig_poller  = ThreadPollOuput(self.input['events'])
        self.trig_poller.new_data.connect(self.on_new_trig)
        
        self.wait_list = []
        self.recreate_stack()
        
        
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def on_params_change(self):
        pass

    def on_new_trig(self, pos, data):
        thread = ThreadPollOuputUntilPosLimit(pos+int(self.sample_rate*self.params['right_sweep'], parent = self)
        thread.limit_reached.connect(self.on_limit_reached)
        self.wait_list.append(thread)
        thread.start()
    
    def on_limit_reached(self):
        thread = self.sender()
        pos = thread.pos
        thread.stop()
        thread.wait()
        self.wait_list.pop(thread)

    def recreate_stack(self):
        n = self.stream['nb_channel']
        stack_size = self.allParams['stack_size']
        left_sweep = self.allParams['left_sweep']
        right_sweep = self.allParams['right_sweep']
        sr = self.stream['sampling_rate']

        self.limit1 = l1 = int(left_sweep*sr)
        self.limit2 = l2 = int(right_sweep*sr)
        
        self.t_vect = np.arange(l2-l1)/sr+left_sweep
        self.stack = np.zeros((stack_size, n, l2-l1), dtype = self.stream.shared_array.dtype)
        self.stack_pos = 0
        
        self.total_trig = 0

    def reset_stack(self):
        self.stack[:] = 0
        self.stack_pos = 0
        
        self.total_trig = 0


