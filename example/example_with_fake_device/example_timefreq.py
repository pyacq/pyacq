# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, FakeMultiSignals
from pyacq.gui import TimeFreq

import numpy as np

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
                                sampling_rate =20000.,
                                buffer_length = 64.,
                                packet_size = 64,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=TimeFreq(stream = dev.streams[0])
    w1.show()
    #~ w1.change_param_tfr(colormap = 'bone')
    visibles = np.zeros(64, dtype = bool)
    visibles[::3] = True
    #~ visibles[0] = True
    #~ w1.set_params(colormap = 'hot', visibles = visibles, xsize=5, nb_column = 8)
    w1.set_params(colormap = 'jet', visibles = visibles, xsize=10, nb_column = 4)
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
