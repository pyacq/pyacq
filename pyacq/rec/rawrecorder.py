# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np
import collections
import logging
import os
import json

from ..core import Node, register_node_type, ThreadPollInput, InputStream
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from ..version import version as pyacq_version


class RawRecorder(Node):
    """
    Simple recorder Node of multiple streams in raw data format.
    
    Implementation is simple, this launch one thread by stream.
    Each one pull data and write it directly into a file in binary format.
    
    Usage:
    list_of_stream_to_record = [...]
    rec = RawRecorder()
    rec.configure(streams=list_of_stream_to_record, autoconnect=True, dirname=path_of_record)
    
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
        
        self._stream_properties = collections.OrderedDict()
        
        for name, input in self.inputs.items():
            filename = os.path.join(self.dirname, name+'.raw')
            fid = open(filename, mode='wb')
            self.files.append(fid)
            
            thread = ThreadRec(name, input, fid)
            self.threads.append(thread)
            thread.recv_start_index.connect(self.on_start_index)
            
            prop = {}
            for k in ('streamtype', 'dtype', 'shape', 'sample_rate'):
                prop[k] = input.params[k]
            self._stream_properties[name] = prop
        
        self._stream_properties['pyacq_version'] = pyacq_version
        
        self._flush_stream_properties()
        
        self._annotations = {}
    
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
    
    def on_start_index(self, name, start_index):
        self._stream_properties[name]['start_index'] = start_index
        self._flush_stream_properties()
    
    def _flush_stream_properties(self):
        filename = os.path.join(self.dirname, 'stream_properties.json')
        _flush_dict(filename, self._stream_properties)
    
    def add_annotations(self, **kargs):
        self._annotations.update(kargs)
        filename = os.path.join(self.dirname, 'annotations.json')
        _flush_dict(filename, self._annotations)
    

def _flush_dict(filename, d):
        with open(filename, mode = 'w', encoding = 'utf8') as f:
            f.write(json.dumps(d, sort_keys=True,
                            indent=4, separators=(',', ': '), ensure_ascii=False))



class ThreadRec(ThreadPollInput):
    recv_start_index = QtCore.Signal(str, int)
    def __init__(self, name, input_stream,fid, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout=timeout, return_data=True, parent=parent)
        self.name = name
        self.fid = fid
        self._start_index = None
        
    def process_data(self, pos, data):
        if self._start_index is None:
            self._start_index = int(pos - data.shape[0])
            self.recv_start_index.emit(self.name, self._start_index)
        
        #~ print(self.input_stream().name, 'pos', pos, 'data.shape', data.shape)
        self.fid.write(data.tobytes())
    
        
register_node_type(RawRecorder)
