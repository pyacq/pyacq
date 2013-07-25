# -*- coding: utf-8 -*-
"""

Very simple acquisition with a fake multi signal device.

"""

from pyacq import StreamHandler, EmotivMultiSignals

import zmq
import msgpack
import time
import multiprocessing as mp




def test_recv_loop(port, stop_recv):
    print 'start receiver loop' , port
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE,'')
    socket.connect("tcp://localhost:{}".format(port))
    while stop_recv.value==0:
        message = socket.recv()
        pos = msgpack.loads(message)
        print 'On port {} read pos is {}'.format( port, pos)
    print 'stop receiver'


def run_Emotiv():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = EmotivMultiSignals(streamhandler = streamhandler)
    dev.configure(buffer_length = 1800) 
    dev.initialize()
    dev.start()
    
    # Create and starts receiver with multuprocessing
    stream0 = dev.streams[0]
    stop_recv = mp.Value('i', 0)
    process = mp.Process(target= test_recv_loop, args = (stream0['port'],stop_recv))
    process.start()
    time.sleep(10.)
    stop_recv.value = 1
    process.join()
        
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    run_Emotiv()
