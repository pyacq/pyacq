import time
import timeit
import pytest
import sys

from pyacq.core.stream import OutputStream, InputStream
import numpy as np


protocols = ['tcp', 'inproc', 'ipc']  # 'udp' is not working
if sys.platform.startswith('win'):
    protocols.remove('ipc')
compressions = ['', 'blosc-blosclz', 'blosc-lz4']


def test_stream_plaindata():
    nb_channel = 16
    chunksize = 1024
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*', 
                       transfermode='plaindata', streamtype='analogsignal',
                       dtype='float32', shape=(-1, nb_channel), compression ='',
                       scale = None, offset = None, units = '')
    
    for protocol in protocols:
        for compression in compressions:
            print(protocol, compression)
            stream_spec['protocol'] = protocol
            stream_spec['compression'] = compression
            outstream = OutputStream()
            outstream.configure(**stream_spec)
            
            instream = InputStream()
            instream.connect(outstream)
            time.sleep(.5)
            
            index = 0
            for i in range(5):
                #~ print(i)
                # send
                index += chunksize
                arr = np.random.rand(1024, nb_channel).astype(stream_spec['dtype'])
                outstream.send(index, arr, autoswapaxes=False)
                
                # recv
                index2, arr2 = instream.recv(autoswapaxes=False)
                assert index2==index
                assert np.all((arr-arr2)==0.)
        
            outstream.close()
            instream.close()
            #~ print()


def test_stream_sharedarray():
    # this test is perform with no autoswapaxes
    #~ nb_channel = 16
    nb_channel = 1
    
    chunksize = 1024
    ring_size = chunksize * 5 - 334
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', port='*',
                        transfermode='sharedarray', streamtype='analogsignal',
                        dtype='float32', shape=(-1, nb_channel), timeaxis = 0, compression ='',
                        scale = None, offset = None, units = '',
                        sharedarray_shape = (ring_size, nb_channel), ring_buffer_method= 'single',
                        )
    protocol = 'tcp'
    for ring_buffer_method in['single', 'double',]:
        for timeaxis in [0, 1]:
            print('sharedarray', ring_buffer_method, 'timeaxis', timeaxis)
            stream_spec['ring_buffer_method'] = ring_buffer_method
            stream_spec['timeaxis'] = timeaxis
            if timeaxis == 0:
                stream_spec['shape'] = (-1, nb_channel)
                stream_spec['sharedarray_shape'] = (ring_size, nb_channel)
            elif timeaxis == 1:
                stream_spec['shape'] = (nb_channel, -1)
                stream_spec['sharedarray_shape'] = (nb_channel, ring_size)
            outstream = OutputStream()
            outstream.configure(**stream_spec)
            instream = InputStream()
            instream.connect(outstream)
            time.sleep(.5)
            
            index = 0
            for i in range(30):
                #~ print(i)
                
                # send
                if timeaxis==0:
                    arr = np.tile(np.arange(index, index+chunksize)[:, None], (1,nb_channel)).astype(stream_spec['dtype'])
                elif timeaxis==1:
                    arr = np.tile(np.arange(index, index+chunksize)[None,:], (nb_channel, 1)).astype(stream_spec['dtype'])
                index += chunksize
                outstream.send(index, arr, autoswapaxes=False)
                
                index2, arr2 = instream.recv(autoswapaxes=False, with_data = False)
                
                assert index2==index
                assert arr2 is None
                
                # get a buffer of size chunksize*3
                if ring_buffer_method == 'double' and index>chunksize*3:
                    arr2 = instream.get_array_slice(index2, chunksize*3, autoswapaxes=False)
                    if timeaxis==0:
                        assert np.all(arr2[:,0]==np.arange(index-chunksize*3, index).astype('float32'))
                    elif timeaxis==1:
                        assert np.all(arr2[0,:]==np.arange(index-chunksize*3, index).astype('float32'))
            
            outstream.close()
            instream.close()
            #~ print()


def benchmark_stream():
    setup = """
from pyacq.core.stream  import OutputStream, InputStream
import numpy as np
import time

nb_channel = 16
chunksize = {chunksize}
ring_size = chunksize*20
nloop = {nloop}
stream_spec = dict(protocol = {protocol}, interface = '127.0.0.1', port = '*',
                    transfertmode = {transfertmode}, streamtype = 'analogsignal',
                    dtype = 'float32', shape = (-1, nb_channel), compression ={compression},
                    scale = None, offset = None, units = '',
                    # for sharedarray
                    sharedarray_shape = ( ring_size, nb_channel), timeaxis = 0,
                    ring_buffer_method = 'double',
                        )
outstream = OutputStream()
outstream.configure(**stream_spec)
time.sleep(.5)
instream = InputStream()
instream.connect(outstream)

arr = np.random.rand(chunksize, nb_channel).astype(stream_spec['dtype'])
def start_loop(outstream, instream):
    index = 0
    for i in range(nloop):
        index += chunksize
        outstream.send(index, arr)
        index2, arr2 = instream.recv()
    """
    
    stmt = """
start_loop(outstream, instream)
outstream.close()
instream.close()
    """
    
    for chunksize, nloop in [(2**10, 10), (2**14, 1), (2**16, 10)]:
        print('#'*5)
        for protocol in protocols:            
            for compression in compressions:
                setup2 = setup.format(compression=repr(compression), protocol=repr(protocol), transfertmode="'plaindata'",
                            chunksize=chunksize, nloop=nloop)
                t = timeit.timeit(stmt, setup=setup2, number=1)
                print(chunksize, nloop, 'plaindata', protocol, compression, 'time =', t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'Mo/s')
        
        setup2 = setup.format(compression="''", protocol="'tcp'", transfertmode="'sharedarray'",
                    chunksize=chunksize, nloop=nloop)
        t = timeit.timeit(stmt, setup=setup2, number=1)
        print(chunksize, nloop, 'sharedarray', 'time =', t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'Mo/s')
        

def test_autoswapaxes():
    # the recv shape is alwas (10,2)
    nb_channel = 2
    l = 10
    data = np.empty((10, nb_channel), dtype = 'float32')
    assert data.flags['C_CONTIGUOUS']
    
    # timeaxis 0 / plaindata
    outstream, instream  = OutputStream(),InputStream()
    outstream.configure(transfermode = 'plaindata', timeaxis=0, shape = (-1,nb_channel))
    instream.connect(outstream)
    time.sleep(.5)
    outstream.send(l, data)
    pos, data2 = instream.recv()
    assert data2.shape == (l,2)
    assert data2.flags['C_CONTIGUOUS']
    
    # timeaxis 1 / plaindata
    outstream, instream  = OutputStream(),InputStream()
    outstream.configure(transfermode = 'plaindata', timeaxis=1, shape = (nb_channel, -1))
    instream.connect(outstream)
    time.sleep(.5)
    outstream.send(l, data)
    pos, data2 = instream.recv()
    assert data2.shape == (l,2)
    assert not data2.flags['C_CONTIGUOUS']
    

    # timeaxis 0 / sharedarray
    outstream, instream  = OutputStream(),InputStream()
    outstream.configure(transfermode = 'sharedarray', timeaxis=0, shape = (-1,nb_channel),
                    sharedarray_shape = (l*5, nb_channel), ring_buffer_method = 'double')
    instream.connect(outstream)
    assert instream.receiver._numpyarr.flags['C_CONTIGUOUS']
    assert not instream.receiver._numpyarr[:, 0].flags['C_CONTIGUOUS']
    time.sleep(.5)
    outstream.send(l, data)
    pos, data2 = instream.recv(with_data = True)
    assert data2.flags['C_CONTIGUOUS']
    assert data2.shape == (l,2)
    

    # timeaxis 1 / sharedarray
    outstream, instream  = OutputStream(),InputStream()
    outstream.configure(transfermode = 'sharedarray', timeaxis=1, shape = (nb_channel, -1),
                    sharedarray_shape = (nb_channel, l*5), ring_buffer_method = 'double')
    instream.connect(outstream)
    assert instream.receiver._numpyarr.flags['C_CONTIGUOUS']
    assert  instream.receiver._numpyarr[0, :].flags['C_CONTIGUOUS']
    time.sleep(.5)
    outstream.send(l, data)
    pos, data2 = instream.recv(with_data = True)
    assert not data2.flags['C_CONTIGUOUS']
    assert data2.shape == (l,2)
    
    
    
    
    
    
    
    

if __name__ == '__main__':
    test_stream_plaindata()
    test_stream_sharedarray()
    #benchmark_stream()
    test_autoswapaxes()

