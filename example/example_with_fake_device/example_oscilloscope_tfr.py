# -*- coding: utf-8 -*-
"""
Oscilloscope  and tfr example
"""

from pyacq import StreamHandler, FakeMultiSignals
from pyacq.gui import Oscilloscope
from pyacq.gui import TimeFreq

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
    dev.configure( 
                                nb_channel = 32,
                                sampling_rate =1000.,
                                buffer_length = 64.,
                                packet_size = 16,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    w1.set_params(refresh_interval = 40,
                                                        xsize = 2.)
    w1.auto_gain_and_offset(mode = 2)
    w1.show()
    
    w2 = TimeFreq(stream = dev.streams[0], max_visible_on_open = 4)
    w2.set_params(refresh_interval = 40,
                                                        xsize = 2., nb_column = 1)
    w2.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
