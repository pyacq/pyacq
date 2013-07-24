# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, FakeMultiSignals
from pyacq.gui import Oscilloscope

import msgpack
#~ import gevent
#~ import zmq.green as zmq

from PyQt4 import QtCore,QtGui

import zmq
import msgpack
import time

def test1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( name = 'Test dev',
                                nb_channel = 64,
                                sampling_rate =1000.,
                                buffer_length = 6.4,
                                packet_size = 10,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = dev.stream)
    w1.show()
    w1.auto_gain_and_offset(mode = 2)
    w1.change_param_global(xsize = 1.)

    w2=Oscilloscope(stream = dev.stream)
    w2.show()
    w2.auto_gain_and_offset(mode = 0)
    w2.change_param_global(xsize = 5, mode = 'scroll')
    

    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
