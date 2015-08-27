import time
import timeit
import pytest
import sys

from pyacq.core.stream  import OutputStream, InputStream
import numpy as np


protocols = ['tcp', 'inproc', 'ipc']#'udp' is not working
if sys.platform.startswith('win'):
    protocols.remove('ipc')
compressions = ['', 'blosc-blosclz', 'blosc-lz4']

def test_stream_plaindata():
    nb_channel = 16
    chunksize = 1024
    stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port='*', 
                       transfermode = 'plaindata', streamtype = 'analogsignal',
                       dtype = 'float32', shape = (-1, nb_channel), compression ='',
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
                #send
                index += chunksize
                arr = np.random.rand(1024, nb_channel).astype(stream_spec['dtype'])
                outstream.send(index, arr)
                
                #recv
                index2, arr2 = instream.recv()
                assert index2==index
                assert np.all((arr-arr2)==0.)
        
            outstream.close()
            instream.close()
            #~ print()


def test_stream_sharedarray():
    #~ nb_channel = 16
    nb_channel = 1
    
    chunksize = 1024
    ring_size = chunksize * 5 - 334
    stream_spec = dict(protocol = 'tcp', interface = '127.0.0.1', port = '*',
                        transfermode = 'shared_array', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, nb_channel), time_axis = 0, compression ='',
                        scale = None, offset = None, units = '',
                        shared_array_shape = ( ring_size, nb_channel), ring_buffer_method= 'single',
                        )
    protocol = 'tcp'
    for ring_buffer_method in['single', 'double',]:
        for time_axis in [0, 1]:
            print('shared_array', ring_buffer_method, 'time_axis', time_axis)
            stream_spec['ring_buffer_method'] = ring_buffer_method
            stream_spec['time_axis'] = time_axis
            if time_axis == 0:
                stream_spec['shape'] =  (-1, nb_channel)
                stream_spec['shared_array_shape'] =  ( ring_size, nb_channel)
            elif time_axis == 1:
                stream_spec['shape'] =  (nb_channel, -1)
                stream_spec['shared_array_shape'] =  (nb_channel,  ring_size)
            outstream = OutputStream()
            outstream.configure(**stream_spec)
            instream = InputStream()
            instream.connect(outstream)
            time.sleep(.5)
            
            index = 0
            for i in range(30):
                #~ print(i)
                
                #send
                if time_axis==0:
                    arr = np.tile(np.arange(index, index+chunksize)[:, None], (1,nb_channel)).astype(stream_spec['dtype'])
                elif time_axis==1:
                    arr = np.tile(np.arange(index, index+chunksize)[None ,:], (nb_channel, 1)).astype(stream_spec['dtype'])
                index += chunksize
                outstream.send(index, arr)
                
                index2, arr2 = instream.recv()
                
                assert index2==index
                assert arr2 is None
                
                # get a buffer of size chunksize*3
                if ring_buffer_method == 'double' and index>chunksize*3:
                    arr2 = instream.get_array_slice(index2, chunksize*3)
                    if time_axis==0:
                        assert np.all(arr2[:,0]==np.arange(index-chunksize*3, index).astype('float32'))
                    elif time_axis==1:
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
                    shared_array_shape = ( ring_size, nb_channel), time_axis = 0,
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
    
    for chunksize, nloop in [(2**10, 10),  (2**14, 1), (2**16, 10)]:
        print('#'*5)
        for protocol in protocols:            
            for compression in compressions:
                setup2 = setup.format(compression = repr(compression), protocol = repr(protocol), transfertmode = "'plaindata'",
                            chunksize = chunksize, nloop = nloop)
                t = timeit.timeit(stmt, setup = setup2,  number = 1)
                print(chunksize, nloop, 'plaindata', protocol, compression, 'time =', t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'Mo/s')
        
        setup2 = setup.format(compression = "''", protocol = "'tcp'", transfertmode = "'shared_array'",
                    chunksize = chunksize, nloop = nloop)
        t = timeit.timeit(stmt, setup = setup2,  number = 1)
        print(chunksize, nloop,  'shared_array', 'time =', t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'Mo/s')
        
        
        
        

if __name__ == '__main__':
    test_stream_plaindata()
    test_stream_sharedarray()
    #benchmark_stream()

