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
    
    def assert_is_fill(data):
        if np.isnan(fill):
            assert np.all(np.isnan(data))
        else:
            assert np.all(data == fill)
    
    def assert_array_eq(a, b):
        ma = np.isnan(a)
        mb = np.isnan(b)
        assert (a.shape == b.shape)
        assert np.all(ma == mb)
        assert np.all(a[~ma] == b[~mb]) 
    
    buf1 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=False)
    buf2 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=True)
    buf3 = RingBuffer(shape=(10, 5, 7), dtype=np.float, double=False)
    buf4 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=True, axisorder=(1, 2, 0))
    buf5 = RingBuffer(shape=(10, 5, 7), dtype='float32', double=False, axisorder=(1, 2, 0))
    
    for buf, fill in [(buf1, 0), (buf2, 0), (buf3, np.nan), (buf4, 0), (buf5, np.nan)]:
        assert_is_fill(buf[-10:])
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
            
        # add a chunk, test the data and boundaries have updated correctly
        d = np.ones((5, 5, 7), dtype=buf.dtype)
        buf.new_chunk(d)
        assert buf[1].shape == (5, 7)
        assert buf[:].shape == (10, 5, 7)
        assert buf[:, 2, 1:3].shape == (10, 2)
        assert np.all(buf[-5:] == 1)
        assert np.all(buf[0:] == buf[-5:])
        assert buf[-5:].shape == d.shape
        assert buf[-5:].dtype == d.dtype
        assert_is_fill(buf[-10:-5])

        # test native axis order
        order = np.argsort(buf[:].strides)[::-1]
        assert np.all(order == buf.axisorder)
    
        # test another chunk
        buf.new_chunk(d[:3]*2)
        assert buf[:].shape == (10, 5, 7)
        assert np.all(buf[-3:] == 2)
        assert np.all(buf[5:] == buf[-3:])
        assert np.all(buf[-8:-3] == 1)
        assert np.all(buf[-8:-3] == buf[0:5])
        assert_is_fill(buf[-10:-8])
        
        # test a chunk that crosses the ring break
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

        # test native axis order
        order = np.argsort(buf[:].strides)[::-1]
        assert np.all(order == buf.axisorder)

        # new chunk with skipped data
        buf.new_chunk(d*4, index=buf.last_index() + 7)
        assert buf[:].shape == (10, 5, 7)
        assert np.all(buf[-5:] == 4)
        assert_is_fill(buf[-7:-5])
        assert np.all(buf[-10:-7] == 3)
        
        # check extra indices
        assert_array_eq(buf[::-1], buf[:][::-1])
        
        buf.new_chunk(d*5, index=buf.last_index() + 15)
        assert buf[:].shape == (10, 5, 7)
        assert np.all(buf[-5:] == 5)
        assert_is_fill(buf[-10:-5])
        
        # check extra indices
        i = buf.first_index()
        assert_array_eq(buf[::-1], buf[:][::-1])
        assert_array_eq(buf[::-2], buf[:][::-2])
        assert_array_eq(buf[i+5::-3], buf[:][5::-3])
        assert_array_eq(buf[:i+7:-1], buf[:][:7:-1])
        assert_array_eq(buf[:i+7:-1, 3, ::-2], buf[:][:7:-1, 3, ::-2])
        
        # check copy/no-copy
        buf.new_chunk(np.arange(350).astype(buf.dtype).reshape(10, 5, 7), index=1005)
        a = buf[-4:]
        b = buf[-4:]
        c = buf[-8:]
        d = buf[-8:]
        assert_array_eq(a, b)
        assert_array_eq(c, d)
        a[:] = (np.random.random(size=(4,5,7)) * 100).astype(buf.dtype)
        assert_array_eq(a, b)
        c[:] = (np.random.random(size=(8,5,7)) * 100).astype(buf.dtype)
        if buf.double:
            assert_array_eq(c, d)
        else:
            assert not np.all(c == d)


def test_ringbuffer_shm():
    buf1 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=True, shmem=True, axisorder=(0, 2, 1))
    buf2 = RingBuffer(shape=(10, 5, 7), dtype=np.ubyte, double=True, shmem=buf1.shm_id, axisorder=(0, 2, 1))
    buf1.new_chunk(np.arange(350).astype(buf1.dtype).reshape(10, 5, 7), index=1005)
    assert buf2.last_index() == buf1.last_index()
    assert np.all(buf1[:] == buf2[:])


protocols = ['tcp', 'inproc', 'ipc']  # 'udp' is not working
if sys.platform.startswith('win'):
    protocols.remove('ipc')
compressions = ['', 'blosc-blosclz', 'blosc-lz4']


def test_stream_plaindata():
    for protocol in protocols:
        for compression in compressions:
            check_stream(transfermode='plaindata', protocol=protocol, compression=compression)
            
def test_stream_sharedmem():
    chunksize = 128
    chan_shape = (16,)
    n_shared_chunks = 10
    dtype = 'float32'
    shm_size = chunksize * n_shared_chunks
    for protocol in protocols:
        for compression in compressions:
            check_stream(chunksize=chunksize, chan_shape=chan_shape, buffer_size=shm_size,
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
        if i == 1:
            # send non-aligned data
            cs = (chunk_shape[1], chunk_shape[0]) + chunk_shape[2:]
            arr = np.random.rand(*cs).transpose(1,0).astype(stream_spec['dtype'])
        else:
            arr = np.random.rand(*chunk_shape).astype(stream_spec['dtype'])
        outstream.send(index, arr)
        
        # recv
        index2, arr2 = instream.recv()
        assert index2==index
        assert np.all((arr-arr2)==0.)

    outstream.close()
    instream.close()


def test_plaindata_ringbuffer():
    check_stream_ringbuffer(transfermode='plaindata', buffer_size=4096)
    
def test_sharedmem_ringbuffer():
    check_stream_ringbuffer(transfermode='sharedmem', buffer_size=4096)
    check_stream_ringbuffer(transfermode='sharedmem', buffer_size=4096, axisorder=(1, 0))
    
def check_stream_ringbuffer(**kwds):
    chunk_shape = (-1, 16)
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*', 
                       transfermode='plaindata', streamtype='analogsignal',
                       dtype='float32', shape=chunk_shape, compression='',
                       scale=None, offset=None, units='', axisorder=None)
    stream_spec.update(kwds)
    print("  %s" % kwds)
    
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    
    instream = InputStream()
    instream.connect(outstream)
    time.sleep(.1)
    
    data = np.random.normal(size=(4096, 16)).astype('float32')
    index = -1
    for i in range(16):
        chunk = data[i*256:(i+1)*256]
        index += chunk.shape[0]
        outstream.send(index, chunk)
        instream.recv()
    data2 = instream.get_array_slice(0, 4096)
    assert np.all(data2 == data)
    if outstream.params['axisorder'] is not None:
        assert np.all(np.argsort(data2.strides)[::-1] == outstream.params['axisorder'])
    



if __name__ == '__main__':
    test_stream_plaindata()
    test_stream_sharedarray()
    test_autoswapaxes()

