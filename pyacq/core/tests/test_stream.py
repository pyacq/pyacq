import time
#~ import pytest
#~ import logging

from pyacq.core.stream  import StreamSender, StreamReceiver
import numpy as np


def test_stream_plaindata():
    nb_channel = 16
    chunksize = 1024
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '8002',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, nb_channel), compression ='',
                        scale = None, offset = None, units = '' )
    
    for compression in ['', 'blosc-blosclz', 'blosc-lz4']:
        print(compression)
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
        


if __name__ == '__main__':
    test_stream_plaindata()
