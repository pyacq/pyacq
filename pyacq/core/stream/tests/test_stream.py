import time
import timeit
import pytest
import sys

from pyacq.core.stream import OutputStream, InputStream, RingBuffer
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
    chunksize = 128
    chan_shape = (16,)
    n_shared_chunks = 10
    dtype = 'float32'
    shm_size = chunksize * n_shared_chunks
    for protocol in protocols:
        check_stream(chunksize=chunksize, chan_shape=chan_shape, buffer_size=shm_size,
                     transfermode='sharedmem', protocol=protocol,
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
    
    for i in range(5):
        #~ print(i)
        # send
        if i == 1:
            # send non-aligned data
            cs = (chunk_shape[1], chunk_shape[0]) + chunk_shape[2:]
            arr = np.random.rand(*cs).transpose(1,0).astype(stream_spec['dtype'])
        else:
            arr = np.random.rand(*chunk_shape).astype(stream_spec['dtype'])
        outstream.send(arr)
        
        # recv
        index, arr2 = instream.recv()
        assert index == outstream.last_index
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
    instream.set_buffer(stream_spec['buffer_size'], axisorder=stream_spec['axisorder'])
    
    # Make sure we are re-using sharedmem buffer
    if instream.receiver.buffer is not None:
        assert instream._own_buffer is False
        
    time.sleep(.1)
    
    data = np.random.normal(size=(4096, 16)).astype('float32')
    for i in range(16):
        chunk = data[i*256:(i+1)*256]
        outstream.send(chunk)
        instream.recv()
    data2 = instream[0:4096]
    assert np.all(data2 == data)
    if outstream.params['axisorder'] is not None:
        assert np.all(np.argsort(data2.strides)[::-1] == outstream.params['axisorder'])
    



if __name__ == '__main__':
    test_stream_plaindata()
    test_stream_sharedarray()
    test_autoswapaxes()

