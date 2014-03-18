# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, ComediMultiSignals
from pyacq.gui import Oscilloscope, TimeFreq, OscilloscopeDigital

import msgpack

from PyQt4 import QtCore,QtGui

import zmq
import msgpack
import time
import numpy as np

def test1():

    
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = ComediMultiSignals(streamhandler = streamhandler)
    dev.configure( device_path = '/dev/comedi0',
                                sampling_rate =9555.111,
                                buffer_length = 5.,
                            )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    #w1.auto_gain_and_offset(mode = 0)
    visibles = np.ones(dev.nb_channel, dtype = bool)
    visibles[1:] = False
    w1.set_params(xsize = 3., refresh_interval = 100, 
                                mode = 'scan', ylims = [-1., 1.],
                                visibles = visibles,
                                )
    w1.show()
    
    app.exec_()
    
    dev.stop()
    dev.close()
    w1.stop()



if __name__ == '__main__':
    test1()
