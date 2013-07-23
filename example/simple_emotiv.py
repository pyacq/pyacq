# -*- coding: utf-8 -*-
"""

Very simple acquisition with a fake multi signal device.

"""

from pyacq import StreamHandler, EmotivMultiSignals

import zmq
import msgpack
import time

def run_Emotiv():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = EmotivMultiSignals(streamhandler = streamhandler)
    dev.configure( name = 'Emotiv dev',
                                nb_channel = 14,		# order: [ 'F3', 'FC6', 'P7', 'T8', 'F7','F8','T7','P8','AF4','F4','AF3','O2','O1','FC5','X','Y']
                                nb_impedance = 14, 
                                buffer_length = 6.4,    # doit être un multiple du packet size
                                packet_size = 1,
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
    while time.time()-t0<10.:
        # loop during 10s
        message = socket.recv()
        pos = msgpack.loads(message)
        # pos is absolut so need modulo
        ind1 = last_pos%half_size+half_size
        ind2 = pos%half_size+half_size
        print 'pos', pos, ' time', time.time()-t0, 'np_array.shape:', np_array[:,ind1:ind2].shape
        last_pos = pos
    
        
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    run_Emotiv()
