# -*- coding: utf-8 -*-
"""
Simple test with measurement computing.


"""

from pyacq import StreamHandler, MeasurementComputingMultiSignals

import zmq
import msgpack
import time

import multiprocessing as mp

def test1():
    # Device list
    streamhandler = StreamHandler()
    # Get devices list
    dev = MeasurementComputingMultiSignals(streamhandler = streamhandler)
    for n, info in MeasurementComputingMultiSignals.get_available_devices().items():
        print n ,info
    
def test_recv_loop(port, stop_recv):

    print('start rcv loop',port)
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE,'')
    socket.connect("tcp://localhost:{}".format(port))
    while stop_recv.value==0:
        message = socket.recv()
        pos = msgpack.loads(message)
        #~ print('On port {} read pos is {}'.format( port, pos))
    print('stop recv')




def test2():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = MeasurementComputingMultiSignals(streamhandler = streamhandler)
    dev.configure( board_num = 0,
                          sampling_rate =10000.,
                          buffer_length = 5.,
                          #~ channel_indexes = range(64),
                          channel_indexes = [0,4,7,  16],
                          #~ channel_indexes = [0],
                          digital_port = [0, 1, 2],
                          #~ digital_port = [],
                                )
    dev.initialize()
    dev.start()

    stop_recv = mp.Value('i', 0)
    process = mp.Process(target= test_recv_loop, args = (dev.streams[0]['port'],stop_recv))
    process.start()

    process = mp.Process(target= test_recv_loop, args = (dev.streams[1]['port'],stop_recv))
    process.start()
    
    
    time.sleep(20.)
    stop_recv.value = 1
    process.join()
    
    # Stope and release the device
    dev.stop()
    dev.close()

def print_digital_port(stop_recv, stream):
    port = stream['port']
    arr = stream['shared_array'].to_numpy_array()
    print 'start rcv loop',port
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE,'')
    socket.connect("tcp://localhost:{}".format(port))
    while stop_recv.value==0:
        message = socket.recv()
        pos = msgpack.loads(message)
        pos = pos%arr.shape[1]/2 + arr.shape[1]/2
        print arr[:,pos]
        #~ print('On port {} read pos is {}'.format( port, pos))
    print 'stop recv'

def test3():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = MeasurementComputingMultiSignals(streamhandler = streamhandler)
    dev.configure( board_num = 0,
                          sampling_rate =10000.,
                          buffer_length = 5.,
                          channel_indexes = [0, ],
                          #~ channel_indexes = [0],
                          digital_port = [0, 1, 2],
                          #~ digital_port = [],
                                )
    dev.initialize()
    dev.start()

    stop_recv = mp.Value('i', 0)
    process = mp.Process(target= print_digital_port, args = (stop_recv, dev.streams[1]))
    process.start()
    
    time.sleep(20.)
    stop_recv.value = 1
    process.join()
    
    
    # Stope and release the device
    dev.stop()
    dev.close()


if __name__ == '__main__':
    #~ test1()
    #~ test2()
    test3()
