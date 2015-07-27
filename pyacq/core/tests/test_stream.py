import time
import timeit
import pytest

from pyacq.core.stream  import StreamSender, StreamReceiver
import numpy as np


def test_stream_plaindata():
    nb_channel = 16
    chunksize = 1024
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfermode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, nb_channel), time_axis = 0, compression ='',
                        scale = None, offset = None, units = '' )
    
    for protocol in ['tcp',  'inproc', 'ipc']: #'udp' is not working
        for compression in ['', 'blosc-blosclz', 'blosc-lz4']:
            print(protocol, compression)
            stream_dict['protocol'] = protocol
            stream_dict['compression'] = compression
            sender = StreamSender(**stream_dict)
            time.sleep(.5)
            receiver = StreamReceiver(**stream_dict)
            
            index = 0
            for i in range(5):
                print(i)
                #send
                index += chunksize
                arr = np.random.rand(1024, nb_channel).astype(stream_dict['dtype'])
                sender.send(index, arr)
                
                #recv
                index2, arr2 = receiver.recv()
                assert index2==index
                assert np.all((arr-arr2)==0.)
        
            sender.close()
            receiver.close()

    
def benchmark_stream():
    setup = """
from pyacq.core.stream  import StreamSender, StreamReceiver
import numpy as np
import time

nb_channel = 16
chunksize = {chunksize}
nloop = {nloop}
stream_dict = dict(protocol = {protocol}, interface = '127.0.0.1', port = {port},
                    transfertmode = 'plaindata', streamtype = 'analogsignal',
                    dtype = 'float32', shape = (-1, nb_channel), compression ={compression},
                    scale = None, offset = None, units = '' )
sender = StreamSender(**stream_dict)
time.sleep(.5)
receiver = StreamReceiver(**stream_dict)

arr = np.random.rand(1024, nb_channel).astype(stream_dict['dtype'])
def start_loop(sender, receiver):
    index = 0
    for i in range(nloop):
        index += chunksize
        sender.send(index, arr)
        index2, arr2 = receiver.recv()
    """
    
    stmt = """
start_loop(sender, receiver)
    """
    
    port = 9500
    for chunksize, nloop in [(2**10, 100),  (2**14, 10), (2**16, 10)]:
        for protocol in ['tcp', 'inproc', 'ipc']: # 'udp',
            print()
            for compression in ['', 'blosc-blosclz', 'blosc-lz4']:
                port = port+1
                setup2 = setup.format(compression = repr(compression), protocol = repr(protocol), port = port,
                            chunksize = chunksize, nloop = nloop)
                t = timeit.timeit(stmt, setup = setup2,  number = 1)
                print(chunksize, nloop,  protocol, compression, 'time =', t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'Mo/s')
                time.sleep(1.)
    

def test_stream_sharedarray():
    #~ nb_channel = 16
    nb_channel = 1
    
    chunksize = 1024
    ring_size = chunksize * 5 - 334
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfermode = 'shared_array', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, nb_channel), time_axis = 0, compression ='',
                        scale = None, offset = None, units = '',
                        shared_array_shape = ( ring_size, nb_channel), ring_buffer_method= 'single',
                        )
    protocol = 'tcp'
    for ring_buffer_method in['single', 'double',]:
        for time_axis in [0, 1]:
            print(ring_buffer_method, 'time_axis', time_axis)
            stream_dict['ring_buffer_method'] = ring_buffer_method
            stream_dict['time_axis'] = time_axis
            if time_axis == 0:
                stream_dict['shape'] =  (-1, nb_channel)
                stream_dict['shared_array_shape'] =  ( ring_size, nb_channel)
            elif time_axis == 1:
                stream_dict['shape'] =  (nb_channel, -1)
                stream_dict['shared_array_shape'] =  (nb_channel,  ring_size)
            sender = StreamSender(**stream_dict)
            time.sleep(.5)
            print('shm_id', sender.params['shm_id'])
            receiver = StreamReceiver(**sender.params)
            time.sleep(.5)
            index = 0
            for i in range(30):
                print(i)
                
                #send
                if time_axis==0:
                    arr = np.tile(np.arange(index, index+chunksize)[:, None], (1,nb_channel)).astype(stream_dict['dtype'])
                    #~ arr = np.random.rand(chunksize, nb_channel).astype(stream_dict['dtype'])
                elif time_axis==1:
                    arr = np.tile(np.arange(index, index+chunksize)[None ,:], (nb_channel, 1)).astype(stream_dict['dtype'])
                    #~ arr = np.random.rand(nb_channel, chunksize).astype(stream_dict['dtype'])
                index += chunksize
                sender.send(index, arr)
            
                #recv
                index2, arr2 = receiver.recv()
                assert index2==index
                assert arr2 is None
                
                # get a buffer of size chunksize*3
                if ring_buffer_method == 'double' and index>chunksize*3:
                    arr2 = receiver.get_array_slice(index2, chunksize*3)
                    if time_axis==0:
                        assert np.all(arr2[:,0]==np.arange(index-chunksize*3, index).astype('float32'))
                    elif time_axis==1:
                        assert np.all(arr2[0,:]==np.arange(index-chunksize*3, index).astype('float32'))
            
            sender.close()
            receiver.close()
    


if __name__ == '__main__':
    test_stream_plaindata()
    #benchmark_stream()
    test_stream_sharedarray()

