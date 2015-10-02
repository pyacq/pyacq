from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex
import weakref
import numpy as np
from collections import OrderedDict
import logging

from .node import Node, register_node_type
from .stream import OutputStream

import time

class ThreadPollInput(QtCore.QThread):
    """
    Thread that pool in backgroup an InputStream (zmq.SUB).
    Util for Node that have inputs.    
    
    By default it emit signal (new_data) but process_data can be override.
    
    """
    new_data = QtCore.Signal(int,object)
    def __init__(self, input_stream, timeout = 200, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.input_stream = weakref.ref(input_stream)
        self.timeout = timeout
        
        self.running = False
        self.lock = Mutex()
        self._pos = None
    
    def run(self):
        with self.lock:
            self.running = True
        
        while True:
            with self.lock:
                if not self.running:
                    break
                if self.input_stream() is None:
                    logging.info("ThreadPollInput has lost InputStream")
                    break
            ev = self.input_stream().poll(timeout = self.timeout)
            if ev>0:
                self._pos, data = self.input_stream().recv()
                self.process_data(self._pos, data)
    
    def process_data(self, pos, data):
        #This can be override to chnage behavior
        self.new_data.emit(self._pos, data)
    
    def stop(self):
        with self.lock:
            self.running = False
    
    def pos(self):
        return self._pos




class ThreadStreamConverter(ThreadPollInput):
    def __init__(self, input_stream, output_stream, conversions,timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.output_stream = weakref.ref(output_stream)
        self.conversions = conversions
    
    def process_data(self, pos, data):
        if 'transfermode' in self.conversions and self.conversions['transfermode'][0]=='sharedarray':
            data = self.input_stream().get_array_slice(self, pos, None)
        if 'timeaxis' in self.conversions:
            data = data.swapaxes(*self.conversions['timeaxis'])
        self.output_stream().send(pos, data)


class StreamConverter(Node):
    """
    A Node that can convert a stream to another stream.
    For instance:
        * convert transfer mode 'plaindata' to 'sharedarray'. (to get a local long buffer)
        * convert dtype 'int32' to 'float64'
        * change timeaxis 0 to 1 (in fact a transpose)
        * ...
    
    usage:
    conv = StreamConverter()
    conv.configure()
    conv.input.connect(someinput)
    conv.output.configure(someotherspec)
    conv.initialize()
    conv.start()
    
    
    """
    _input_specs = {'in' : {}}
    _output_specs = {'out' : {}}
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def _configure(self, **kargs):
        pass
    
    def _initialize(self):
        self.conversions = { }
        # check convertion
        for k in self.input.params:
            if k in ('port', 'protocol', 'interface', 'dtype'):
                continue # the OutputStream/InputStream already do it
            
            old, new = self.input.params[k], self.output.params[k]
            if old != new and old is not None:
                self.conversions[k] = (old, new)
                
        #DO some check ???
        #if 'shape' in self.conversions:
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



class ThreadStreamSplitter(ThreadPollInput):
    """
    
    """
    def __init__(self, input_stream, outputs_stream, channelaxis, nb_channel, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.outputs_stream = weakref.WeakValueDictionary()
        self.outputs_stream.update(outputs_stream)
        self.channelaxis = channelaxis
        self.nb_channel = nb_channel
    
    def process_data(self, pos, data):
        if self.channelaxis == 1:
            for i in range(self.nb_channel):
                self.outputs_stream[str(i)].send(pos, data[:, i:i+1].copy())
        else:
            for i in range(self.nb_channel):
                self.outputs_stream[str(i)].send(pos, data[i:i+1, :])


class StreamSplitter(Node):
    """
    StreamSplitter take a multi signal as input and split it as N single signal output.
    
    Work only for  transfermode = 'plaindata'.
    
    usage:
    splitter = StreamSplitter()
    splitter.configure()
    splitter.input.connect(someinput)
    for output in splitter.outputs.values():
        output.configure(someotherspec)
    splitter.initialize()
    splitter.start()
    
    """
    _input_specs = {'in' : {}}
    _output_specs = {}#done dynamically in _configure
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def _configure(self):
        pass
    
    def check_input_specs(self):
        assert self.input.params['transfermode'] == 'plaindata', 'StreamSplitter work only for transfermode=plaindata'

    def check_output_specs(self):
        for output in self.outputs.values():
            if self.input.params['timeaxis']==0:
                assert output.params['shape'][1] == 1, 'StreamSplitter: wrong shape'
            else:
                assert output.params['shape'][0] == 1, 'StreamSplitter: wrong shape'

    def after_input_connect(self, inputname):
        if self.input.params['timeaxis']==0:
            self.channelaxis = 1
            self.nb_channel = self.input.params['shape'][1]
            shape = (-1, 1)
        else:
            self.channelaxis = 0
            self.nb_channel = self.input.params['shape'][0]
            shape = (1, -1)

        stream_spec = {}
        stream_spec.update(self.input.params)
        stream_spec['shape'] = shape
        stream_spec['port'] = '*'
        #overwrite
        self.outputs = OrderedDict()
        for i in range(self.nb_channel):
            output = OutputStream(spec = stream_spec)
            self.outputs[str(i)] = output
    
    def after_output_configure(self, outputname):
        pass
        
    def _initialize(self):
        self.thread = ThreadStreamSplitter( self.input, self.outputs, self.channelaxis, self.nb_channel)
    
    def _start(self):
        self.thread.start()

    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def _close(self):
        pass

register_node_type(StreamSplitter)
