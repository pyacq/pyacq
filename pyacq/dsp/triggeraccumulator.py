# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

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
    Node that accumulate in a ring buffer chunk of a multi signals on trigger events.
    
    This Node have no output because the stack  size of signals chunks is online configurable.
    sharred memory is difficult because shape can change.
    
    The internal self.stack have 3 dims:
        0 -  trigger 
        1 - nb channel
        2 - times
    
    The self.total_trig indicate the number of triggers since the last reset_stack().
    
    TriggerAccumulator.params['stask_size'] control the number of event in the stack.
    Note the stask behave as a ring buffer along the axis 0.
    So if  self.total_trig>stask_size you need to play with modulo to acces the last event.
    
    On each new chunk this new_chunk is emmited.
    Note that this do not occurs on new trigger but a bit after when the right_sweep is reached on signals stream.
    
    
    """
    _input_specs = {'signals' : dict(streamtype = 'signals'), 
                                'events' : dict(streamtype = 'events',  shape = (-1, )), #dtype ='int64',
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
        self.params = pg.parametertree.Parameter.create( name='Accumulator options',
                                                    type='group', children =self._default_params)
    
    def _configure(self, max_stack_size = 10, max_xsize=2., events_dtype_field = None):
        """
        Arguments
        ---------------
        max_stack_size: int
            maximum size for the event size
        max_xsize: int 
            maximum sample chunk size
        events_dtype_field : None or str
            Standart dtype for 'events' input is 'int64',
            In case of complex dtype (ex : dtype = [('index', 'int64'), ('label', 'S12), ) ] you can precise which
            filed is the index.
            
        
        """
        self.params.sigTreeStateChanged.connect(self.on_params_change)
        self.max_stack_size = max_stack_size
        self.events_dtype_field = events_dtype_field
        self.params.param('stack_size').setLimits([1, self.max_stack_size])
        self.max_xsize = max_xsize
    
    def after_input_connect(self, inputname):
        if inputname == 'signals':
            self.nb_channel = self.inputs['signals'].params['shape'][1]
            self.sample_rate = self.inputs['signals'].params['sample_rate']
        elif inputname == 'events':
            dt = np.dtype(self.inputs['events'].params['dtype'])
            if dt=='int64':
                assert self.events_dtype_field is None,'events_dtype_field is not None but dtype is int64'
            else:
                assert self.events_dtype_field in dt.names, 'events_dtype_field not in input dtype {}'.format(dt)
    
    def _initialize(self):
        buf_size = int(self.inputs['signals'].params['sample_rate'] * self.max_xsize)
        self.inputs['signals'].set_buffer(size=buf_size, axisorder=[1,0], double=True)
        
        self.trig_poller  = ThreadPollInput(self.inputs['events'], return_data=True)
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
            if self.events_dtype_field is None:
                self.limit_poller.append_limit(trig_index+self.limit2)
            else:
                self.limit_poller.append_limit(trig_index[ self.events_dtype_field]+self.limit2)
    
    def on_limit_reached(self, limit_index):
        arr = self.inputs['signals'].get_data(limit_index-self.size, limit_index).transpose()
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


