# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np
import collections
import logging

from ..core import Node, register_node_type, ThreadPollInput, InputStream
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex
import os


class RawRecorder(Node):
    """
    Simple recorder Node of multiple streams in raw data format.
    
    Implementation is simple, this launch one thread by stream.
    Each one pull data and write it directly into a file in binary format.
    
    Usage:
    list_of_stream_to_record = [...]
    rec = RawRecorder()
    rec.configure(streams=list_of_stream_to_record, attocinnect=True, dirname=path_of_record)
    
    """

    _input_specs = {}
    _output_specs = {}
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def _configure(self, streams=[], autoconnect=True, dirname=None):
        self.streams = streams
        self.dirname = dirname
        
        assert not os.path.exists(dirname), 'dirname already exists'
        
        #make inputs
        self.inputs = collections.OrderedDict()
        for i, stream in enumerate(streams):
            name = 'input{}'.format(i)
            input = InputStream(spec={}, node=self, name=name)
            self.inputs[name] = input
            if autoconnect:
                input.connect(stream)
                
    def _initialize(self):
        os.mkdir(self.dirname)
        self.files = []
        self.threads = []
        for name, input in self.inputs.items():
            filename = os.path.join(self.dirname, name+'.raw')
            fid = open(filename, mode='wb')
            self.files.append(fid)
            
            thread = ThreadRec(input, fid)
            self.threads.append(thread)
    
    def _start(self):
        for thread in self.threads:
            thread.start()

    def _stop(self):
        for thread in self.threads:
            thread.stop()
            thread.wait()
        
        #test in any pending data in streams
        for i, (name, input) in enumerate(self.inputs.items()):
            ev = input.poll(timeout=0.2)
            if ev>0:
                pos, data = input.recv(return_data=True)
                self.files[i].write(data.tobytes())
        
        for f in self.files:
            f.close()

    def _close(self):
        pass



class ThreadRec(ThreadPollInput):
    def __init__(self, input_stream,fid, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout=timeout, return_data=True, parent=parent)
        self.fid = fid
        
    def process_data(self, pos, data):
        
        print(self.input_stream().name, 'pos', pos, 'data.shape', data.shape)
        self.fid.write(data.tobytes())
    
        
register_node_type(RawRecorder)
