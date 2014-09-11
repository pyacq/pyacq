# -*- coding: utf-8 -*-
"""

"""

import multiprocessing as mp
import numpy as np
import msgpack

from PyQt4 import QtCore,QtGui
import pyqtgraph as pg

import threading

import zmq

import time


from .base import ProcessingBase


#TODO put this in tools for processing
class WaitLimitThread(QtCore.QThread):
    """
    thread for waiting in a stream a pos.
    """
    limit_reached = QtCore.pyqtSignal(int)
    def __init__(self, parent=None, socket = None, pos_limit = None):
        QtCore.QThread.__init__(self, parent)
        self.running = False
        self.socket = socket
        self.pos_limit = pos_limit
    
    def run(self):
        message = self.socket.recv()
        pos = msgpack.loads(message)
        
        self.running = True
        while self.running:
            events = self.socket.poll(50)
            if events ==0:
                time.sleep(.05)
                continue
            message = self.socket.recv()
            pos = msgpack.loads(message)
            
            if pos>=self.pos_limit:
                self.limit_reached.emit(self.pos_limit)
                self.running = False
                break
            
    
    def stop(self):
        self.running = False
    
    
        



class StackedChunkOnTrigger(ProcessingBase, QtCore.QObject):
    """
    This handle a stack of chunk of signals when there is a trigger.
    """
    new_chunk = QtCore.pyqtSignal(int)
    _param_global = [
            {'name': 'left_sweep', 'type': 'float', 'value': -1., 'step': 0.1,'suffix': 's', 'siPrefix': True},
            {'name': 'right_sweep', 'type': 'float', 'value': 1., 'step': 0.1, 'suffix': 's', 'siPrefix': True},
            { 'name' : 'stack_size', 'type' :'int', 'value' : 1,  'limits':[1,np.inf] },
        ]
    
    def __init__(self, stream,  parent = None, **kargs):
        
        ProcessingBase.__init__(self, stream)
        QtCore.QObject.__init__(self, parent)
        
        
        #TODO : do something with inheritences
        self.allParams = pg.parametertree.Parameter.create( name='Global options',
                                                    type='group', children =self._param_global)
        for k, v in kargs.items():
            try:
                self.allParams[k] = v
            except:
                pass
                
        self.allParams.sigTreeStateChanged.connect(self.on_param_change)
        
        self.np_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.np_array.shape[1]/2
        self.threads_limit = [ ]
        
        self.recreate_stack()
    
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

    def on_param_change(self, params, changes):
        for param, change, data in changes:
            if change != 'value': continue
            #~ print param.name()
            if param.name()=='stack_size':
                self.recreate_stack()
            if param.name() in ['left_sweep', 'right_sweep']:
                self.recreate_stack()
    
    
    def on_trigger(self, pos):
        socket = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(self.stream['port']))
        thread = WaitLimitThread(socket = socket, pos_limit = self.limit2+pos)
        thread.limit_reached.connect(self.on_limit_reached)
        self.threads_limit.append(thread)
        thread.start()

    def on_limit_reached(self, limit):
        self.threads_limit.remove(self.sender())
        
        head = limit%self.half_size+self.half_size
        tail = head - (self.limit2 - self.limit1)
        self.stack[self.stack_pos,:,:] = self.np_array[:, tail:head]
        
        self.stack_pos +=1
        self.stack_pos = self.stack_pos%self.allParams['stack_size']
        self.total_trig += 1
        
        self.new_chunk.emit(self.total_trig)
