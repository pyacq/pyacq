from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex
import weakref
import numpy as np

from .node import Node, register_node_type


class ThreadPollInput(QtCore.QThread):
    """
    Thread that pool in backgroup an InputStream (zmq.SUB).
    And emit Signal.
    Util for Node that have inputs.    
    """
    new_data = QtCore.Signal(int,object)
    def __init__(self, input_stream, timeout = 200, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.input_stream = weakref.ref(input_stream)
        self.timeout = timeout
        
        self.running = False
        self.lock = Mutex()
    
    def run(self):
        with self.lock:
            self.running = True
        
        while True:
            with self.lock:
                if not self.running:
                    break
            
            ev = self.input_stream().poll(timeout = self.timeout)
            if ev>0:
                pos, data = self.input_stream().recv()
                self.new_data.emit(pos, data)

    def stop(self):
        with self.lock:
            self.running = False


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
        
        self.poller = ThreadPollInput(input_stream = self.input)
        self.poller.new_data.connect(self.on_new_data)
    
    def on_new_data(self, pos, arr):
        if 'transfermode' in self.conversions and self.conversions['transfermode'][0]=='sharedarray':
            arr = self.input.get_array_slice(self, pos, None)

        if 'timeaxis' in self.conversions:
            arr = arr.swapaxes(*self.conversions['timeaxis'])
        
        self.output.send(pos, arr)
    
    def _start(self):
        self.poller.start()

    def _stop(self):
        self.poller.stop()
        self.poller.wait()
    
    def _close(self):
        pass


register_node_type(StreamConverter)
