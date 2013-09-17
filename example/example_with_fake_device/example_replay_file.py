# -*- coding: utf-8 -*-
"""
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
import numpy as np

def test1():
    streamhandler = StreamHandler()
    
    filename = 'cerveau_alex.raw'
    precomputed = np.fromfile(filename , dtype = np.float32).reshape(-1, 14).transpose()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = 14,
                                sampling_rate =128.,
                                buffer_length = 30.,
                                packet_size = 1,
                                precomputed = precomputed,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = dev.streams[0])
    w1.show()
    w1.auto_gain_and_offset(mode = 1)
    w1.change_param_global(xsize = 10.)

    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
