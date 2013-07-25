# -*- coding: utf-8 -*-
"""

Very simple acquisition with a fake multi signal device.

"""

from pyacq import StreamHandler, FakeMultiSignals

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



def test1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( name = 'Test dev',
                                nb_channel = 10,
                                sampling_rate =1000.,
                                buffer_length = 6.4,
                                packet_size = 128,
                                )
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
    

    # Stop and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
