# -*- coding: utf-8 -*-
"""
Oscilloscope example.
2 instances simultaneous with differents parameters
"""

from pyacq import StreamHandler, FakeMultiSignals
from pyacq.gui import Oscilloscope, TriggeredOscilloscope

import msgpack
#~ import gevent
#~ import zmq.green as zmq

from PyQt4 import QtCore,QtGui

import zmq
import msgpack
import time

import numpy as np

def test1():
    streamhandler = StreamHandler()
    
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( 
                                #~ nb_channel = 16,
                                #~ sampling_rate =1000.,
                                #~ buffer_length = 64,
                                #~ packet_size = 100,
                                nb_channel = 8,
                                sampling_rate =10000.,
                                buffer_length = 64,
                                packet_size = 100,
                                
                                last_channel_is_trig = True,
                                
                                )
    dev.initialize()
    print dev.streams[0]
    print dev.streams[0]['port']
    dev.start()
    
    app = QtGui.QApplication([])
    
    w1=TriggeredOscilloscope(stream = dev.streams[0])
    w1.set_params(channel = dev.nb_channel-1,
                                    
                                    left_sweep = -.1,
                                    right_sweep = +.3,
                                    threshold = .25,
                                    #~ debounce_mode = 'no-debounce',
                                    debounce_mode = 'after-stable',
                                    #~ debounce_mode = 'before-stable',
                                    debounce_time = 0.05,
                                    )
    w1.show()

    w2=Oscilloscope(stream = dev.streams[0])
    w2.show()
    w2.auto_gain_and_offset(mode = 0)
    w2.set_params(xsize = 5, mode = 'scroll')
    

    
    app.exec_()
    w1.stop()
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
