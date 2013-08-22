# -*- coding: utf-8 -*-

from pyacq import StreamHandler, FakeMultiSignals

import time

def test1():
    streamhandler = StreamHandler()
    
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( name = 'Test dev',
                                nb_channel = 16,
                                sampling_rate =1000.,
                                buffer_length = 64,
                                packet_size = 10,
                                )
    dev.initialize()
    dev.start()
    
    
    
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
