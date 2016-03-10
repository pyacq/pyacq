import time
import timeit
import pytest
import sys

from pyacq.core.stream import OutputStream, InputStream, is_contiguous, RingBuffer
import numpy as np


def test_ringbuffer():
    buf1 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=False)
    buf2 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=True)
    
    for buf in (buf1, buf2):
        assert np.all(buf[-10:] == 0)
        with pytest.raises(IndexError):
            buf[-11]
        with pytest.raises(IndexError):
            buf[1]
            
            
        d = np.ones((5, 5, 7), dtype=buf.dtype)
        buf.new_chunk(d)
        assert buf[1].shape == (5, 7)
        assert buf[:].shape == (10, 5, 7)
        assert buf[:, 2, 1:3].shape == (10, 2)
        assert np.all(buf[-5:] == 1)
        assert np.all(buf[0:] == buf[-5:])
        assert buf[-5:].shape == d.shape
        assert buf[-5:].dtype == d.dtype
        assert np.all(buf[-10:-5] == 0)
    
        buf.new_chunk(d[:3]*2)
        assert np.all(buf[-3:] == 2)
        assert np.all(buf[5:] == buf[-3:])
        assert np.all(buf[-8:-3] == 1)
        assert np.all(buf[-8:-3] == buf[0:5])
        assert np.all(buf[-10:-8] == 0)
        
        buf.new_chunk(d*3)
        with pytest.raises(IndexError):
            buf[-11]
        with pytest.raises(IndexError):
            buf[0]
        assert np.all(buf[-10:-8] == 1)
        assert np.all(buf[-8:-5] == 2)
        assert np.all(buf[-5:] == 3)
        assert np.all(buf[3:5] == 1)
        assert np.all(buf[5:8] == 2)
        assert np.all(buf[8:] == 3)



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

