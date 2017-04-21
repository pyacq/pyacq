import struct
import numpy as np
try:
    import blosc
    HAVE_BLOSC = True
except ImportError:
    HAVE_BLOSC = False

from .streamhelpers import DataSender, DataReceiver, register_transfermode
from .arraytools import is_contiguous, decompose_array, make_dtype


class PlainDataSender(DataSender):
    """Helper class to send data serialized over socket.
    
    To avoid unnecessary copies (and thus optimize transmission speed), data is
    sent exactly as it appears in memory including array strides.
    
    This class supports compression.
    """
    def send(self, index, data):
        # optional pre-processing before send
        if isinstance(data, np.ndarray):
            for f in self.funcs:
                index, data = f(index, data)
                
        # serialize
        dtype = data.dtype
        shape = data.shape
        buf, offset, strides = decompose_array(data)
        
        # compress
        comp = self.params['compression']
        if comp.startswith('blosc-'):
            assert HAVE_BLOSC, "Cannot use blosclz4 compression; blosc package is not importable."
            buf = blosc.compress(buf, data.itemsize, cname=comp[6:])
        elif comp != '':
            raise ValueError("Unknown compression method '%s'" % comp)
        
        # Pack and send
        stat = struct.pack('!' + 'Q' * (3+len(shape)) + 'q' * len(strides), len(shape), index, offset, *(shape + strides))
        copy = self.params.get('copy', False)
        self.socket.send_multipart([stat, buf], copy=copy)


class PlainDataReceiver(DataReceiver):
    """Helper class to receive data serialized over socket.
    
    See PlainDataSender.
    """
    def __init__(self, socket, params):
        DataReceiver.__init__(self, socket, params)
    
    def recv(self, return_data=True):
        # receive and unpack structure
        stat, data = self.socket.recv_multipart()
        ndim = struct.unpack('!Q', stat[:8])[0]
        stat = struct.unpack('!' + 'Q' * (ndim + 2) + 'q' * ndim, stat[8:])
        index = stat[0]
        
        if not return_data:
            return index, None
        
        offset = stat[1]
        shape = stat[2:2+ndim]
        strides = stat[-ndim:]
        
        # uncompress
        comp = self.params['compression']
        if comp.startswith('blosc-'):
            assert HAVE_BLOSC, "Cannot use blosc decompression; blosc package is not importable."
            data = blosc.decompress(data)
        elif comp != '':
            raise ValueError("Unknown compression method '%s'" % comp)
        
        # convert to array
        dtype = make_dtype(self.params['dtype'])
        #~ dtype = self.params['dtype']
        data = np.ndarray(buffer=data, shape=shape,
                          strides=strides, offset=offset, dtype=dtype)        
        return index, data


register_transfermode('plaindata', PlainDataSender, PlainDataReceiver)
