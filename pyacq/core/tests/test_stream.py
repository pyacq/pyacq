import time
import timeit
import pytest
import sys

from pyacq.core.stream import OutputStream, InputStream, is_contiguous
import numpy as np


protocols = ['tcp', 'inproc', 'ipc']  # 'udp' is not working
if sys.platform.startswith('win'):
    protocols.remove('ipc')
compressions = ['', 'blosc-blosclz', 'blosc-lz4']


def test_stream_plaindata():
    for protocol in protocols:
        for compression in compressions:
            check_stream(transfermode='plaindata', protocol=protocol, compression=compression)
            
def test_stream_sharedmem():
    chunksize = 1024
    chan_shape = (16,)
    n_shared_chunks = 10
    dtype = 'float32'
    shm_size = chunksize * np.product(chan_shape) * np.dtype(dtype).itemsize * n_shared_chunks
    for protocol in protocols:
        for compression in compressions:
            check_stream(chunksize=chunksize, chan_shape=chan_shape, sharedmem_size=shm_size,
                         transfermode='sharedmem', protocol=protocol, compression=compression,
                         dtype=dtype)
            
def check_stream(chunksize=1024, chan_shape=(16,), **kwds):
    chunk_shape = (chunksize,) + chan_shape
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*', 
                       transfermode='plaindata', streamtype='analogsignal',
                       dtype='float32', shape=chunk_shape, compression='',
                       scale=None, offset=None, units='')
    stream_spec.update(kwds)
    print("  %s" % kwds)
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    
    instream = InputStream()
    instream.connect(outstream)
    time.sleep(.1)
    
    index = 0
    for i in range(5):
        #~ print(i)
        # send
        index += chunksize
        arr = np.random.rand(*chunk_shape).astype(stream_spec['dtype'])
        outstream.send(index, arr)
        
        # recv
        index2, arr2 = instream.recv()
        assert index2==index
        assert np.all((arr-arr2)==0.)
        if is_contiguous(arr):
            assert arr.strides == arr2.strides
        else:
            # output must at least have the same stride order and direction,
            # even if they don't have the same value
            s1 = np.array(arr.strides)
            s2 = np.array(arr2.strides)
            assert np.all(np.argsort(s1) == np.argsort(s2))
            assert np.all(s1/s1.abs() == s2/s2.abs())

    outstream.close()
    instream.close()


if __name__ == '__main__':
    test_stream_plaindata()
    test_stream_sharedarray()
    test_autoswapaxes()

