import time
import timeit
#~ import pytest
#~ import logging

from pyacq.core.stream  import StreamSender, StreamReceiver
import numpy as np


def test_stream_plaindata():
    nb_channel = 16
    chunksize = 1024
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1',
                       transfermode = 'plaindata', streamtype = 'analogsignal',
                       dtype = 'float32', shape = (-1, nb_channel), compression ='',
                       scale = None, offset = None, units = '')
    
    for protocol in ['tcp',  'inproc', 'ipc']: #'udp' is not working
        for compression in ['', 'blosc-blosclz', 'blosc-lz4']:
            print(protocol, compression)
            stream_dict['protocol'] = protocol
            stream_dict['compression'] = compression
            sender = StreamSender(port='*', **stream_dict)
            time.sleep(.5)
            receiver = StreamReceiver(port=sender.port, **stream_dict)
            
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
    


if __name__ == '__main__':
    test_stream_plaindata()
    benchmark_stream()
