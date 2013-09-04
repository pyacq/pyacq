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

def test1():

    
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = ComediMultiSignals(streamhandler = streamhandler)
    dev.configure( device_path = '/dev/comedi0',
                                sampling_rate =10000.,
                                buffer_length = 5.,
                            )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    #w1.auto_gain_and_offset(mode = 0)
    for i in range(dev.nb_channel):
        w1.change_param_channel(i, visible = i==0)
    w1.change_param_global(xsize = 3., refresh_interval = 100, mode = 'scan', ylims = [-1., 1.])
    w1.show()
    
    app.exec_()
    
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
