# -*- coding: utf-8 -*-
"""
Oscilloscope  and tfr example
"""

from pyacq import StreamHandler, FakeMultiSignals, TimestampServer
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
    dev.configure( name = 'Test dev',
                                nb_channel = 14,
                                sampling_rate =128.,
                                buffer_length = 64.,
                                packet_size = 1,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.stream)
    w1.change_param_global(refresh_interval = 40,
                                                        xsize = 2.)
    w1.show()
    
    w2 = TimeFreq(stream = dev.stream, max_visible_on_open = 14)
    w2.change_param_global(refresh_interval = 40,
                                                        xsize = 2.)
    w2.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
