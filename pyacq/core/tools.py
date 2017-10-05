# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time
import weakref
import logging
import atexit
import numpy as np
import zmq
from collections import OrderedDict
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from .node import Node, register_node_type
from .stream import OutputStream, InputStream


class ThreadPollInput(QtCore.QThread):
    """Thread that polls an InputStream in the background and emits a signal
    when data is received.
    
    This class is used where low-latency response to data is needed within a Qt
    main thread (because polling from the main thread with QTimer either 
    introduces too much latency or consumes too much CPU).
    
    The `process_data()` method may be reimplemented to define other behaviors.
    """
    new_data = QtCore.Signal(int,object)
    def __init__(self, input_stream, timeout=200, return_data=None, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.input_stream = weakref.ref(input_stream)
        self.timeout = timeout
        self.return_data = return_data
        if self.return_data is None:
            self.return_data = self.input_stream()._own_buffer
        
        self.running = False
        self.running_lock = Mutex()
        self.lock = Mutex()
        self._pos = None
        atexit.register(self.stop)
    
    def run(self):
        with self.running_lock:
            self.running = True
        
        while True:
            with self.running_lock:
                if not self.running:
                    break
            if self.input_stream() is None:
                logging.info("ThreadPollInput has lost InputStream")
                break
            ev = self.input_stream().poll(timeout=self.timeout)
            if ev>0:
                try:
                    pos, data = self.input_stream().recv(return_data=self.return_data)
                except zmq.error.ContextTerminated:
                    self.stop()
                    return
                with self.lock:
                    self._pos = pos
                self.process_data(self._pos, data)
    
    def process_data(self, pos, data):
        """This method is called from the polling thread when a new data chunk
        has been received. The default implementation emits the `new_data`
        signal with the updated stream position and the data chunk as arguments.
        
        This method can be overriden.
        """
        self.new_data.emit(pos, data)
    
    def stop(self):
        """Request the polling thread to stop.
        """
        with self.running_lock:
            self.running = False
    
    def pos(self):
        """Return the current stream position.
        """
        with self.lock:
            return self._pos


class ThreadPollOutput(ThreadPollInput):
    """    
    Thread that monitors an OutputStream in the background and emits a Qt signal
    when data is sent.

    Like ThreadPollInput, this class can be used where low-latency response to data
    is needed within a Qt main thread (because polling from the main thread with
    QTimer either introduces too much latency or consumes too much CPU).

    The `process_data()` method may be reimplemented to define other behaviors.
    
    This is class also create internally its own `InputStream`.
    And pull it the same way than ThreadPollInput.
    """
    def __init__(self, output_stream, **kargs):
        self.instream = InputStream()
        self.instream.connect(output_stream)
        ThreadPollInput.__init__(self, self.instream, **kargs)


class ThreadStreamConverter(ThreadPollInput):
    """Thread that polls for data on an input stream and converts the transfer
    mode or time axis of the data before relaying it through its output.
    """
    def __init__(self, input_stream, output_stream, conversions,timeout=200, parent=None):
        ThreadPollInput.__init__(self, input_stream, timeout=timeout, return_data=True, parent=parent)
        self.output_stream = weakref.ref(output_stream)
        self.conversions = conversions
    
    def process_data(self, pos, data):
        #~ if 'transfermode' in self.conversions and self.conversions['transfermode'][0]=='sharedmem':
            #~ data = self.input_stream().get_array_slice(self, pos, None)
        #~ if 'timeaxis' in self.conversions:
            #~ data = data.swapaxes(*self.conversions['timeaxis'])
        if data.dtype!=self.output_stream().params['dtype']:
            data = data.astype(self.output_stream().params['dtype'])
        self.output_stream().send(data, index=pos)


class StreamConverter(Node):
    """
    A Node that converts one stream type to another.
    
    For instance:
    
    * convert transfer mode 'plaindata' to 'sharedarray'. (to get a local long buffer)
    * convert dtype 'int32' to 'float64'
    * change timeaxis 0 to 1 (in fact a transpose)
    * ...
    
    Usage::
    
        conv = StreamConverter()
        conv.configure()
        conv.input.connect(someinput)
        conv.output.configure(someotherspec)
        conv.initialize()
        conv.start()
    
    
    """
    _input_specs = {'in': {}}
    _output_specs = {'out': {}}
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def _configure(self, **kargs):
        pass
    
    def _initialize(self):
        self.conversions = {}
        # check convertion
        for k in self.input.params:
            if k in ('port', 'protocol', 'interface', 'dtype'):
                continue  # the OutputStream/InputStream already do it
            
            old, new = self.input.params.get(k, None), self.output.params.get(k, None)
            if old != new and old is not None:
                self.conversions[k] = (old, new)
                
        # DO some check ???
        # if 'shape' in self.conversions:
        #    assert 'timeaxis' in self.conversions        
        self.thread = ThreadStreamConverter(self.input, self.output, self.conversions)
    
    def _start(self):
        self.thread.start()

    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def _close(self):
        pass

register_node_type(StreamConverter)


class ThreadSplitter(ThreadPollInput):
    def __init__(self, input_stream, outputs_stream, output_channels, timeout=200, parent=None):
        ThreadPollInput.__init__(self, input_stream, timeout=timeout, return_data=True, parent=parent)
        self.outputs_stream = weakref.WeakValueDictionary()
        self.outputs_stream.update(outputs_stream)
        self.output_channels = output_channels
    
    def process_data(self, pos, data):
        for k , chans in self.output_channels.items():
            self.outputs_stream[k].send(data[:, chans], index=pos)


class ChannelSplitter(Node):
    """
    ChannelSplitter take a multi-channel input signal stream and splits it
    into several sub streams.
    
    Usage::
    
        splitter = StreamSplitter()
        splitter.configure(output_channels = { 'out0' : [1,2,3], 'out1' : [4,5,6] })
        splitter.input.connect(someinput)
        for output in splitter.outputs.values():
            output.configure(someotherspec)
        splitter.initialize()
        splitter.start()
        
    """
    _input_specs = {'in': {}}
    _output_specs = {}  # done dynamically in _configure
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def _configure(self, output_channels = {}):
        """
        Params
        -----------
        output_channels: dict of list
            This contain a dict of sub channel list.
            Each key will be the name of each output.
        output_timeaxis: int or 'same'
            The output timeaxis is set here.
        """
        self.output_channels = output_channels
    
    def after_input_connect(self, inputname):
        
        nb_channel =  self.input.params['shape'][1]
        self.outputs = OrderedDict()
        for k, chans in self.output_channels.items():
            assert min(chans)>=0 and max(chans)<nb_channel, 'output_channels do not match channel count {}'.format(nb_channel)

            stream_spec = dict(streamtype='analogsignal', dtype=self.input.params['dtype'],
                                                sample_rate=self.input.params['sample_rate'])
            stream_spec['port'] = '*'
            stream_spec['nb_channel'] = len(chans)
            stream_spec['shape'] = (-1, len(chans))
            output = OutputStream(spec=stream_spec)
            self.outputs[k] = output
    
    def _initialize(self):
        self.thread = ThreadSplitter(self.input, self.outputs, self.output_channels)
    
    def _start(self):
        self.thread.start()

    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def _close(self):
        pass

register_node_type(ChannelSplitter)
