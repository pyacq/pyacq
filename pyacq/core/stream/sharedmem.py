import struct
import numpy as np

from .streamhelpers import DataSender, DataReceiver, register_transfermode
from .ringbuffer import RingBuffer


class SharedMemSender(DataSender):
    """
    """
    def __init__(self, socket, params):
        DataSender.__init__(self, socket, params)
        self.size = self.params['buffer_size']
        dtype = np.dtype(self.params['dtype'])
        shape = (self.size,) + self.params['shape'][1:]
        self._buffer = RingBuffer(shape=shape, dtype=self.params['dtype'],
                                  shmem=True, axisorder=self.params['axisorder'])
        self.params['shm_id'] = self._buffer.shm_id
    
    def send(self, index, data):
        assert data.dtype == self.params['dtype']
        shape = data.shape
        if self.params['shape'][0] != -1:
            assert shape == self.params['shape']
        else:
            assert shape[1:] == self.params['shape'][1:]
 
        self._buffer.new_chunk(data, index)
        
        stat = struct.pack('!' + 'Q' * (2+len(shape)), len(shape), index, *shape)
        self.socket.send_multipart([stat])


class SharedMemReceiver(DataReceiver):
    def __init__(self, socket, params):
        # init data receiver with no ring buffer; we will implement our own from shm.
        DataReceiver.__init__(self, socket, params)

        self.size = self.params['buffer_size']
        shape = (self.size,) + self.params['shape'][1:]
        self.buffer = RingBuffer(shape=shape, dtype=self.params['dtype'],
                                  shmem=self.params['shm_id'], axisorder=self.params['axisorder'])

    def recv(self):
        stat = self.socket.recv_multipart()[0]
        ndim = struct.unpack('!Q', stat[:8])[0]
        stat = struct.unpack('!' + 'Q' * (ndim + 1), stat[8:])
        index = stat[0]
        shape = stat[1:1+ndim]
        data = self.buffer[index+1-shape[0]:index+1]
        return index, data


register_transfermode('sharedmem', SharedMemSender, SharedMemReceiver)
