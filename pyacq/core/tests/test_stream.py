import time
import timeit
import pytest
import sys

from pyacq.core.stream import OutputStream, InputStream, is_contiguous, RingBuffer
import numpy as np


def test_ringbuffer():
    # Add tests:
    #  ensure copy / no-copy
    #  extra indices, steps, negative steps...
    
    def is_fill(data):
        if np.isnan(fill):
            return np.all(np.isnan(data))
        else:
            return np.all(data == fill)
    
    def array_eq(a, b):
        ma = np.isnan(a)
        mb = np.isnan(b)
        return (a.shape == b.shape) and np.all(ma == mb) and np.all(a[~ma] == b[~mb]) 
    
    buf1 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=False)
    buf2 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=True)
    buf3 = RingBuffer(shape=(10, 5, 7), dtype=np.float, double=False)
    
    for buf, fill in [(buf1, 0), (buf2, 0), (buf3, np.nan)]:
        assert is_fill(buf[-10:])
        with pytest.raises(IndexError):
            buf[-11]
        with pytest.raises(IndexError):
            buf[1]
            
        with pytest.raises(ValueError):
            buf.new_chunk(np.zeros((20, 5, 7), dtype=buf.dtype))
        with pytest.raises(ValueError):
            buf.new_chunk(np.zeros((10, 5, 8), dtype=buf.dtype))
        with pytest.raises(TypeError):
            buf.new_chunk(np.zeros((10, 5, 7), dtype='uint'))
            
        d = np.ones((5, 5, 7), dtype=buf.dtype)
        buf.new_chunk(d)
        assert buf[1].shape == (5, 7)
        assert buf[:].shape == (10, 5, 7)
        assert buf[:, 2, 1:3].shape == (10, 2)
        assert np.all(buf[-5:] == 1)
        assert np.all(buf[0:] == buf[-5:])
        assert buf[-5:].shape == d.shape
        assert buf[-5:].dtype == d.dtype
        assert is_fill(buf[-10:-5])
    
        buf.new_chunk(d[:3]*2)
        assert buf[:].shape == (10, 5, 7)
        assert np.all(buf[-3:] == 2)
        assert np.all(buf[5:] == buf[-3:])
        assert np.all(buf[-8:-3] == 1)
        assert np.all(buf[-8:-3] == buf[0:5])
        assert is_fill(buf[-10:-8])
        
        buf.new_chunk(d*3)
        assert buf[:].shape == (10, 5, 7)
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

        # new chunk with skipped data
        buf.new_chunk(d*4, index=buf.last_index() + 7)
        assert buf[:].shape == (10, 5, 7)
        assert np.all(buf[-5:] == 4)
        assert is_fill(buf[-7:-5])
        assert np.all(buf[-10:-7] == 3)
        
        # check extra indices
        assert array_eq(buf[::-1], buf[:][::-1])
        
        buf.new_chunk(d*5, index=buf.last_index() + 15)
        assert buf[:].shape == (10, 5, 7)
        assert np.all(buf[-5:] == 5)
        assert is_fill(buf[-10:-5])
        
        # check extra indices
        i = buf.first_index()
        assert array_eq(buf[::-1], buf[:][::-1])
        assert array_eq(buf[::-2], buf[:][::-2])
        assert array_eq(buf[i+5::-3], buf[:][5::-3])
        assert array_eq(buf[:i+7:-1], buf[:][:7:-1])
        assert array_eq(buf[:i+7:-1, 3, ::-2], buf[:][:7:-1, 3, ::-2])
        
        # check copy/no-copy
        buf.new_chunk(np.arange(350).astype(buf.dtype).reshape(10, 5, 7), index=1005)
        a = buf[-4:]
        b = buf[-4:]
        c = buf[-8:]
        d = buf[-8:]
        assert array_eq(a, b)
        assert array_eq(c, d)
        a[:] = (np.random.random(size=(4,5,7)) * 100).astype(buf.dtype)
        assert array_eq(a, b)
        c[:] = (np.random.random(size=(8,5,7)) * 100).astype(buf.dtype)
        if buf.double:
            assert array_eq(c, d)
        else:
            assert not array_eq(c, d)
            
        


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

