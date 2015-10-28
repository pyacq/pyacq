from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import numpy as np
from pyqtgraph.util.mutex import Mutex

from ..core import (Node, register_node_type, ThreadPollInput)



class ThreadPollInputUntilPosLimit(ThreadPollInput):
    """
    Thread waiting a futur pos in a stream.
    """
    limit_reached = QtCore.pyqtSignal(int)
    def __init__(self,input_stream,  **kargs):
        ThreadPollInput.__init__(self, input_stream, **kargs)
        
        self.limit_lock = Mutex()
        self.limit_indexes = []
    
    def append_limit(self, limit_index):
        with self.limit_lock:
            self.limit_indexes.append(limit_index)
    
    def is_under_limit(self, pos, limit_index):
        return pos<limit_index
    
    def reset(self):
        with self.limit_lock:
            self.limit_indexes = []
            
    def process_data(self, pos, data):
        with self.limit_lock:
            if len(self.limit_indexes)==0: return
            for limit_index in self.limit_indexes:
                if pos>=limit_index:
                    self.limit_reached.emit(limit_index)
            self.limit_indexes = [limit_index for limit_index in self.limit_indexes if pos<limit_index]
    
    

class TriggerAccumulator(Node,  QtCore.QObject):
    """
    Node that accumulate in a ring buffer chunk of a multi signals stream of trigger events.
    
    This Node have no output because the stack  size of signals chunks is online configurable via, so
    sharred memory is difficult because shape can change.
    
    The internal self.stack have 3 dims:
        0 -  trigger 
        1 - nb channel
        2 - times
    
    The self.total_trig indicate the number of triggers since the last reset_stack().
    
    TriggerAccumulator.params['stask_size'] control the number of event in the stack.
    Note the it behave have a ring buffer along the axis 0.
    So if  self.total_trig>stask_size you need to play with modulo to acces the last event.
    
    On each new chunk this new_chunk is emmited.
    Note that this do not occurs on new trigger but a bit after when the right_sweep is reached on signals stream.
    
    
    """
    _input_specs = {'signals' : dict(streamtype = 'signals', transfermode='sharedarray', timeaxis = 1), 
                                'events' : dict(streamtype = 'events', dtype ='int64', shape = (-1, )),
                                }
    _output_specs = {}
    
    _default_params = [
            {'name': 'left_sweep', 'type': 'float', 'value': -1., 'step': 0.1,'suffix': 's', 'siPrefix': True},
            {'name': 'right_sweep', 'type': 'float', 'value': 1., 'step': 0.1, 'suffix': 's', 'siPrefix': True},
            { 'name' : 'stack_size', 'type' :'int', 'value' : 1,  'limits':[1,np.inf] },
                ]
    
    new_chunk = QtCore.pyqtSignal(int)
    
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
        self.nb_channel, _ = self.inputs['signals'].params['shape']
        self.sample_rate = self.inputs['signals'].params['sample_rate']
    
    def _initialize(self):
        self.trig_poller  = ThreadPollInput(self.inputs['events'])
        self.trig_poller.new_data.connect(self.on_new_trig)
        
        self.limit_poller = ThreadPollInputUntilPosLimit(self.inputs['signals'])
        self.limit_poller.limit_reached.connect(self.on_limit_reached)
        
        self.wait_thread_list = []
        self.recreate_stack()
        
    def _start(self):
        self.trig_poller.start()
        self.limit_poller.start()

    def _stop(self):
        self.trig_poller.stop()
        self.trig_poller.wait()
        self.limit_poller.stop()
        self.limit_poller.wait()
        
        for thread in self.wait_thread_list:
            thread.stop()
            thread.wait()
        self.wait_thread_list = []
    
    def on_params_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            if param.name() in ['stack_size', 'left_sweep', 'right_sweep']:
                self.recreate_stack()
        self.params.param('left_sweep').setLimits([-np.inf, self.params['right_sweep']])
        

    def on_new_trig(self, trig_num, trig_indexes):
        for trig_index in trig_indexes:
            self.limit_poller.append_limit(trig_index+self.limit2)
    
    def on_limit_reached(self, limit_index):
        arr = self.inputs['signals'].get_array_slice(limit_index, self.size)
        if arr is not None:
            self.stack[self.stack_pos,:,:] = arr
            
            self.stack_pos +=1
            self.stack_pos = self.stack_pos%self.params['stack_size']
            self.total_trig += 1
            
            self.new_chunk.emit(self.total_trig)

    def recreate_stack(self):
        self.limit1 = l1 = int(self.params['left_sweep']*self.sample_rate)
        self.limit2 = l2 = int(self.params['right_sweep']*self.sample_rate)
        self.size = l2 - l1
        self.t_vect = np.arange(l2-l1)/self.sample_rate + self.params['left_sweep']
        self.stack = np.zeros((self.params['stack_size'], self.nb_channel, l2-l1), dtype = self.inputs['signals'].params['dtype'])
        self.stack_pos = 0
        self.total_trig = 0
        self.limit_poller.reset()
        

    def reset_stack(self):
        self.stack[:] = 0
        self.stack_pos = 0
        self.total_trig = 0
        self.limit_poller.reset()


