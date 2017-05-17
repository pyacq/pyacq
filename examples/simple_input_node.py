"""
Stream monitor

A simple node that monitors activity on an input stream and prints details about packets
received.

"""
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui

from pyacq.core import Node, register_node_type
from pyacq.core.tools import ThreadPollInput


class StreamMonitor(Node):
    """
    Monitors activity on an input stream and prints details about packets
    received.
    """
    _input_specs = {'signals': {}}
    
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def _configure(self):
        pass

    def _initialize(self):
        self.poller = ThreadPollInput(self.input, return_data=True)
        self.poller.new_data.connect(self.data_received)
        
    def _start(self):
        self.poller.start()
        
    def data_received(self, ptr, data):
        print("Data received: %d %s %s" % (ptr, data.shape, data.dtype))
    
    

# Not necessary for this example, but registering the node class would make it
# easier for us to instantiate this type of node in a remote process via
# Manager.create_node()
register_node_type(StreamMonitor)


if __name__ == '__main__':
    from pyacq.devices import NumpyDeviceBuffer
    app = QtGui.QApplication([])
    
    # Create a data source. This will continuously emit chunks from a numpy
    # array.
    data = np.random.randn(2500, 7).astype('float64')
    dev = NumpyDeviceBuffer()
    # Configure the source such that it emits 50-element chunks twice per second. 
    dev.configure(nb_channel=7, sample_interval=0.01, chunksize=50, buffer=data)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    dev.initialize()
    
    # Create a monitor node
    mon = StreamMonitor()
    mon.configure()
    mon.input.connect(dev.output)
    mon.initialize()

    # start both nodes
    mon.start()
    dev.start()

