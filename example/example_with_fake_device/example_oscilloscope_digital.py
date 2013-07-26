# -*- coding: utf-8 -*-
"""
Oscilloscope example.
2 instances simultaneous with differents parameters
"""

from pyacq import StreamHandler, FakeDigital
from pyacq.gui import OscilloscopeDigital

import msgpack


from PyQt4 import QtCore,QtGui

import zmq
import msgpack
import time

def test1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeDigital(streamhandler = streamhandler)
    dev.configure( name = 'Test dev',
                                nb_channel = 10,
                                sampling_rate =1000.,
                                buffer_length = 60.,
                                packet_size = 20,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    
    w1=OscilloscopeDigital(stream = dev.streams[0])
    w1.show()
    w1.change_param_global(xsize = 5.)

    w2=OscilloscopeDigital(stream = dev.streams[0])
    w2.show()
    w2.change_param_global(xsize = 20, mode = 'scroll')
    

    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
