# -*- coding: utf-8 -*-
"""
Oscilloscope example
"""

from pyacq import StreamHandler, MeasurementComputingMultiSignals
from pyacq.gui import Oscilloscope, TimeFreq, OscilloscopeDigital

import msgpack

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
                          buffer_length = 60.,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    w1.auto_gain_and_offset(mode = 2)
    w1.set_params(xsize = 20., refresh_interval = 100, mode = 'scan', ylims = [-8., 8.])
    w1.show()
    
    w2 = TimeFreq(stream = dev.streams[0], max_visible_on_open = 4)
    w2.set_params(refresh_interval = 100, xsize = 2.)
    w2.show()
    
    w3=OscilloscopeDigital(stream = dev.streams[1])
    w3.set_params(xsize = 20, mode = 'scan')    
    w3.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
