# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, MeasurementComputingMultiSignals
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
    dev = MeasurementComputingMultiSignals(streamhandler = streamhandler)
    dev.configure( board_num = 0,
                          sampling_rate =1000.,
                          buffer_length = 5.12,
                          channel_indexes = range(64),
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.stream)
    w1.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
