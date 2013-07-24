# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, FakeMultiSignals, TimestampServer, EmotivMultiSignals
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
    dev.configure( name = 'Emo Acc',
                                nb_channel = 14,
                                buffer_length = 1800,    # doit être un multiple du packet size
                                packet_size = 1,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.stream)
    w1.show()
    print"ok"

    w2=Oscilloscope(stream = dev.stream)
    w2.show()


    w3=TimeFreq(stream = dev.stream)
    w3.show()    
    
    app.exec_()
    
    
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    emotiv_oscillo()
