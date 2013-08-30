# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, FakeMultiSignals
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
                                nb_channel = 64,
                                sampling_rate =1000.,
                                buffer_length = 64.,
                                packet_size = 128,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=TimeFreq(stream = dev.streams[0])
    w1.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
