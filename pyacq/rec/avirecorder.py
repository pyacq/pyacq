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

try:
    import av
    HAVE_AV = True
except ImportError:
    HAVE_AV = False


class AviRecorder(Node):
    """
    Node to record AVI file.
    This Node aim to be use in conjonction with pyacq.device.WebCamAV
    
    
    
    """

    _input_specs = {}
    _output_specs = {}
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_AV, "AviRecorder node depends on the `av` package, but it could not be imported."
    
    def _configure(self, streams=[], autoconnect=True, dirname=None):
        self.streams = streams
        self.dirname = dirname

        if isinstance(streams, list):
            names = ['video{}'.format(i) for i in range(len(streams))]
        elif isinstance(streams, dict):
            names = list(streams.keys())
            streams = list(streams.values())
        
        #make inputs
        self.inputs = collections.OrderedDict()
        for i, stream in enumerate(streams):
            name = names[i]
            input = InputStream(spec={}, node=self, name=name)
            self.inputs[name] = input
            if autoconnect:
                input.connect(stream)
                
    def _initialize(self):
        if not os.path.exists(self.dirname):
            os.mkdir(self.dirname)
        #~ self.files = []
        self.av_containers = []
        self.av_streams = []
        self.threads = []
        
        self.mutex = Mutex()
        
        self._stream_properties = collections.OrderedDict()
        
        for name, input in self.inputs.items():
            filename = os.path.join(self.dirname, name+'.avi')
            
            sr = input.params['sample_rate']
            print('sr', sr)
            av_container = av.open(filename, mode='w')
            av_stream = av_container.add_stream('h264', rate=sr)
            av_stream.width = input.params['shape'][1]
            av_stream.height = input.params['shape'][0]
            av_stream.pix_fmt = 'yuv420p'
            
            self.av_containers.append(av_container)
            self.av_streams.append(av_stream)
            
            #~ fid = open(filename, mode='wb')
            #~ self.files.append(fid)
            
            thread = ThreadRec(name, input, av_container, av_stream)
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
        for name, input in self.inputs.items():
            input.empty_queue()
        
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
                
                #  TODO take format from stream params need change WebCamAV
                frame = av.VideoFrame.from_ndarray(data, format='rgb24') 
                packet = self.av_streams[i].encode(frame)
                if packet is not None:
                    self.av_containers[i].mux(packet)
        
        # flush stream  = encode empty frame until empty packet
        for i, av_stream in enumerate(self.av_streams):
            for packet in av_stream.encode():
                self.av_containers[i].mux(packet)
        
        # Close files
        for i, av_container in enumerate(self.av_containers):
            av_container.close()
    
    def _close(self):
        pass
    
    def on_start_index(self, name, start_index):
        self._stream_properties[name]['start_index'] = start_index
        self._flush_stream_properties()
    
    def _flush_stream_properties(self):
        filename = os.path.join(self.dirname, 'avi_stream_properties.json')
        with self.mutex:
            _flush_dict(filename, self._stream_properties)
    
    def add_annotations(self, **kargs):
        self._annotations.update(kargs)
        filename = os.path.join(self.dirname, 'annotations.json')
        with self.mutex:
            _flush_dict(filename, self._annotations)
    

def _flush_dict(filename, d):
        with open(filename, mode = 'w', encoding = 'utf8') as f:
            f.write(json.dumps(d, sort_keys=True,
                            indent=4, separators=(',', ': '), ensure_ascii=False))



class ThreadRec(ThreadPollInput):
    recv_start_index = QtCore.Signal(str, int)
    def __init__(self, name, input_stream, av_container, av_stream, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout=timeout, return_data=True, parent=parent)
        self.name = name
        self.av_container = av_container
        self.av_stream = av_stream
        self._start_index = None
        
    def process_data(self, pos, data):
        if self._start_index is None:
            self._start_index = int(pos - 1)
            print('_start_index video', self._start_index)
            self.recv_start_index.emit(self.name, self._start_index)
        
        frame = av.VideoFrame.from_ndarray(data, format='rgb24')
        
        for packet in self.av_stream.encode(frame):
            self.av_container.mux(packet)
        
register_node_type(AviRecorder)
