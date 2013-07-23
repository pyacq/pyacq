# -*- coding: utf-8 -*-
"""

Very simple acquisition with a fake multi signal device.

"""

from pyacq import StreamHandler, MeasurementComputingMultiSignals

import zmq
import msgpack
import time

def test1():
    streamhandler = StreamHandler()
    # Get devices list
    dev = MeasurementComputingMultiSignals(streamhandler = streamhandler)
    for n, info in MeasurementComputingMultiSignals.get_available_devices().items():
        print n ,info
    


def test2():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = MeasurementComputingMultiSignals(streamhandler = streamhandler)
    dev.configure( board_num = 0,
                          sampling_rate =100000.,
                          buffer_length = 5.,
                          channel_indexes = range(64),
                          #~ channel_indexes = [0,4, 16],
                                )
    dev.initialize()
    dev.start()

    # Read the buffer on ZMQ socket
    port = dev.stream['port']
    np_array = dev.stream['shared_array'].to_numpy_array()
    print np_array.shape # this should be (nb_channel x buffer_length*samplign_rate)
    zmq.Context()
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE,'')
    socket.connect("tcp://localhost:{}".format(port))
    t0 = time.time()
    last_pos = 0
    half_size = np_array.shape[1]/2
    while time.time()-t0<30.:
        # loop during 10s
        message = socket.recv()
        pos = msgpack.loads(message)
        # pos is absolut so need modulo
        #~ ind1 = last_pos%half_size+half_size
        ind2 = pos%half_size+half_size
        ind1 = ind2 - (pos-last_pos)
        print 'pos', pos, ' time', time.time()-t0, 'np_array.shape:', np_array[:,ind1:ind2].shape
        last_pos = pos
        
        
    # Stope and release the device
    dev.stop()
    dev.close()


if __name__ == '__main__':
    #~ test1()
    test2()
