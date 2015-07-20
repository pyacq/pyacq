#~ import time
#~ import pytest
#~ import logging

from pyacq.core.stream  import StreamSender, StreamReceiver
import numpy as np


def test_stream():
    nb_channel = 16
    chunksize = 1024
    stream_dict = dict(protocol = 'tcp', addr = '127.0.0.1', port = '8000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, nb_channel), compression ='',
                        scale = None, offset = None, units = '' )
    
    sender = StreamSender(**stream_dict)
    receiver = StreamReceiver(**stream_dict)
    
    index = 0
    for i in range(5):
        #send
        index += chunksize
        arr = np.random.rand(1024, nb_channel).astype(stream_dict['dtype'])
        sender.send(index, arr)
        
        #recv
        index2, arr2 = receiver.recv()
        assert index2==index
        assert np.all((arr-arr2)==0.)


if __name__ == '__main__':
    test_stream()
