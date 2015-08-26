import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui


class NumpyDeviceBuffer(Node):
    _output_specs = {'signals' : dict(streamtype = 'analogsignal',dtype = 'float32',
                                                shape = (-1, 16), compression ='', time_axis=0,
                                                sampling_rate =30.
                                                ),
                                }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def start(self):
        self.timer.start()
        self._running = True

    def stop(self):
        self.timer.stop()
        self._running = False
    
    def close(self):
        pass
    
    def initialize(self):
        self.head = 0
        self.timer = QtCore.QTimer(singleShot = False, interval = int(self.chunksize*self.sample_interval*1000))
        self.timer.timeout.connect(self.send_data)

    def configure(self, nb_channel = 16, sample_interval = 0.001):
        self.nb_channel = nb_channel
        self.sample_interval = sample_interval
        
        self.output.spec['shape'] = (-1, nb_channel)
        self.output.spec['sampling_rate'] = 1./sample_interval
        
        self.nloop = 20
        self.chunksize = 256
        self.length =self.nloop*self.chunksize
        t = np.arange(self.length)
        self.buffer = np.random.rand(self.length, nb_channel)*.2
        self.buffer += np.sin(2*np.pi*10.*t)[:,None]
        self.buffer = self.buffer.astype('float32')
    
    def send_data(self):
        i1 = self.head%self.length
        self.head += self.chunksize
        i2 = self.head%self.length
        self.output.send(self.head, self.buffer[i1:i2, :])

register_node_type(NumpyDeviceBuffer)
