# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, FakeMultiSignals, EmotivMultiSignals
from pyacq.gui import Oscilloscope, TimeFreq

import msgpack
#~ import gevent
#~ import zmq.green as zmq

from PyQt4 import QtCore,QtGui

import zmq
import msgpack
import time

def emotiv_oscillo():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = EmotivMultiSignals(streamhandler = streamhandler)
    dev.configure(buffer_length = 1800)   # doit être un multiple du packet size
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    w1.show()

    w2=Oscilloscope(stream = dev.streams[0])
    w2.show()


    w3=TimeFreq(stream = dev.streams[0])
    w3.show()    
    
    app.exec_()
    
    
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    emotiv_oscillo()
