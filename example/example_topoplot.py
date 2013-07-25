# -*- coding: utf-8 -*-
"""
Topoplot example
"""

from pyacq import StreamHandler, FakeMultiSignals, TimestampServer
from pyacq.gui import Topoplot

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
                                buffer_length = 10.,
                                packet_size = 1,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Topoplot(stream = dev.stream)
    w1.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
