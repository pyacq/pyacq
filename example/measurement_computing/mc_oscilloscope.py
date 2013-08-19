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
                          #~ sampling_rate =1000.,
                          buffer_length = 60.,
                          #~ channel_indexes = range(64),
                          channel_indexes = range(8),
                          #~ channel_indexes = [0,12,25,56],
                          #~ digital_port = [0, 1, 2],
                          digital_port = [],
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    w1.auto_gain_and_offset(mode = 2)
    w1.change_param_global(xsize = 5., refresh_interval = 100, mode = 'scan', ylims = [-8., 8.])
    w1.show()
    
    w2 = TimeFreq(stream = dev.streams[0], max_visible_on_open = 4)
    w2.change_param_global(refresh_interval = 100, xsize = 2.)
    w2.show()
    
    w3=OscilloscopeDigital(stream = dev.streams[1])
    w3.change_param_global(xsize = 20, mode = 'scan')    
    w3.show()
    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
