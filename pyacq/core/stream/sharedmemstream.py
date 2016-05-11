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
        shape = (self.size,) + tuple(self.params['shape'][1:])
        self._buffer = RingBuffer(shape=shape, dtype=self.params['dtype'],
                                  shmem=True, axisorder=self.params['axisorder'],
                                  double=self.params['double'], fill=self.params['fill'])
        self.params['shm_id'] = self._buffer.shm_id
    
    def send(self, index, data):
        assert data.dtype == self.params['dtype']
        shape = data.shape
        if self.params['shape'][0] != -1:
            assert shape == self.params['shape']
        else:
            assert tuple(shape[1:]) == tuple(self.params['shape'][1:])
 
        self._buffer.new_chunk(data, index)
        
        stat = struct.pack('!' + 'QQ', index, shape[0])
        self.socket.send_multipart([stat])


class SharedMemReceiver(DataReceiver):
    def __init__(self, socket, params):
        # init data receiver with no ring buffer; we will implement our own from shm.
        DataReceiver.__init__(self, socket, params)

        self.size = self.params['buffer_size']
        shape = (self.size,) + tuple(self.params['shape'][1:])
        self.buffer = RingBuffer(shape=shape, dtype=self.params['dtype'],
                                 shmem=self.params['shm_id'], axisorder=self.params['axisorder'])

    #~ def recv(self, return_data=True):
    def recv(self, return_data=False):
        """Receive message indicating the index of the next data chunk.
        
        Parameters:
        -----------
        return_data : bool
            If True, return the new data chunk (this may involve copying data
            from the shared ring buffer). If False, then return None in place
            of data (the new data can still be accessed form the buffer).
        """
        stat = self.socket.recv_multipart()[0]
        index, size = struct.unpack('!QQ', stat)
        if return_data:
            data = self.buffer[index-size:index]
        else:
            data = None
        return index, data


register_transfermode('sharedmem', SharedMemSender, SharedMemReceiver)
