import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui


class NumpyDeviceBuffer(Node):
    """A fake analogsignal device.
    
    This node streams data from a predefined buffer in an endless loop.
    """
    _output_specs = {'signals': dict(streamtype='analogsignal',dtype='float32',
                                                shape=(-1, 16), compression ='', timeaxis=0,
                                                sample_rate =30.
                                                )}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def configure(self, *args, **kwargs):
        """
        Parameters for configure
        ---
        nb_channel: int
            Number of output channels.
        sample_interval: float
            Time duration of a single data sample. This determines the rate at
            which data is sent.
        chunksize: int
            Length of chunks to send.
        buffer: array
            Data to send. Must have `buffer.shape[0] == nb_channel`.
        """
        return Node.configure(self, *args, **kwargs)

    def _configure(self, nb_channel=16, sample_interval=0.001, chunksize=256,
                timeaxis=0, buffer=None):
        self.nb_channel = nb_channel
        self.sample_interval = sample_interval
        self.chunksize = chunksize
        self.timeaxis = timeaxis
        
        if self.timeaxis == 0:
            self.output.spec['shape'] = (-1, nb_channel)
            self.output.spec['timeaxis'] = self.timeaxis
            self.channelaxis = 1
        else:
            self.output.spec['shape'] = (nb_channel, -1)
            self.output.spec['timeaxis'] = self.timeaxis
            self.channelaxis = 0
        self.output.spec['sample_rate'] = 1./sample_interval
        
        if buffer is None:
            nloop = 40
            self.length =nloop*self.chunksize
            t = np.arange(self.length)*sample_interval
            self.buffer = np.random.rand(self.length, nb_channel)*.05
            self.buffer += np.sin(2*np.pi*440.*t)[:,None]*.5
            self.buffer = self.buffer.astype('float32')
            if self.timeaxis == 1:
                self.buffer = self.buffer.transpose()
        else:
            assert buffer.shape[self.channelaxis] == self.nb_channel, 'Wrong nb_channel'
            assert buffer.shape[self.timeaxis]%chunksize == 0, 'Wrong buffer.shape[0] not multiple chunksize'
            self.buffer = buffer
            self.length = buffer.shape[self.timeaxis]
    
    def _initialize(self):
        self.head = 0
        self.timer = QtCore.QTimer(singleShot=False, interval=int(self.chunksize*self.sample_interval*1000))
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
        if self.timeaxis==0:
            self.output.send(self.head, self.buffer[i1:i2, :])
        else:
            self.output.send(self.head, self.buffer[:,i1:i2])

register_node_type(NumpyDeviceBuffer)
