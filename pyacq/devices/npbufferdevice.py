import numpy as np

from ..core import Node, register_node
from pyqtgraph.Qt import QtCore, QtGui


class NumpyDeviceBuffer(Node):
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
        assert len(self.out_streams)!=0, 'create_outputs must be call first'
        self.stream =self.out_streams[0]
        self.head = 0
        self.timer = QtCore.QTimer(singleShot = False, interval = int(self.chunksize*self.sample_interval*1000))
        self.timer.timeout.connect(self.send_data)

    def configure(self, nb_channel = 16, sample_interval = 0.001):
        self.nb_channel = nb_channel
        self.sample_interval = sample_interval
        
        self.nloop = 20
        self.chunksize = 256
        self.length =self.nloop*self.chunksize
        t = np.arange(self.length)
        self.buffer = np.random.rand(self.length, nb_channel)*.2
        self.buffer += np.sin(2*np.pi*10.*t)[:,None]
        self.buffer = self.buffer.astype('float32')
    
    def send_data(self):
        print('send_data', self.head)
        import sys
        sys.stdout.flush()
        i1 = self.head%self.length
        self.head += self.chunksize
        i2 = self.head%self.length
        self.out_streams[0].send(self.head, self.buffer[i1:i2, :])

register_node(NumpyDeviceBuffer)