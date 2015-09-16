import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui


class NumpyDeviceBuffer(Node):
    """
    This is a fake analogsignal device
    It send data chunk of a predifined buffer inloop at the approximated speed.
    Done with QTimer.

    Parameters for configure
    ---
    nb_channel: int
    
    sample_interval: float
    
    chunksize: int
    
    buffer: np.ndarray
        This can be used only on local because numpy is not JSON serilized.
    
    """
    _output_specs = {'signals' : dict(streamtype = 'analogsignal',dtype = 'float32',
                                                shape = (-1, 16), compression ='', timeaxis=0,
                                                sampling_rate =30.
                                                )}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def _configure(self, nb_channel = 16, sample_interval = 0.001, chunksize = 256, buffer = None):
        """
        
        """
        self.nb_channel = nb_channel
        self.sample_interval = sample_interval
        self.chunksize = chunksize
        
        self.output.spec['shape'] = (-1, nb_channel)
        self.output.spec['sampling_rate'] = 1./sample_interval
        
        if buffer is None:
            nloop = 40
            self.length =nloop*self.chunksize
            t = np.arange(self.length)*sample_interval
            self.buffer = np.random.rand(self.length, nb_channel)*.05
            self.buffer += np.sin(2*np.pi*440.*t)[:,None]*.5
            self.buffer = self.buffer.astype('float32')
        else:
            assert buffer.shape[1] == self.nb_channel, 'Wrong nb_channel'
            assert buffer.shape[0]%chunksize == 0, 'Wrong buffer.shape[0] not multiple chunksize'
            self.buffer = buffer
            self.length = buffer.shape[0]
    
    def _initialize(self):
        self.head = 0
        self.timer = QtCore.QTimer(singleShot = False, interval = int(self.chunksize*self.sample_interval*1000))
        self.timer.timeout.connect(self.send_data)
    
    def _start(self):
        self.timer.start()

    def _stop(self):
        self.timer.stop()
    
    def _close(self):
        pass
    
    def send_data(self):
        i1 = self.head%self.length
        self.head += self.chunksize
        i2 = i1 + self.chunksize
        self.output.send(self.head, self.buffer[i1:i2, :])

register_node_type(NumpyDeviceBuffer)
