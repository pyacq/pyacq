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
    dev.configure( 
                                nb_channel = 30,
                                sampling_rate =1000000.,
                                buffer_length = 60.,
                                packet_size = 20,
                                )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    
    #~ w1=OscilloscopeDigital(stream = dev.streams[0])
    #~ w1.show()
    #~ w1.set_params(xsize = 5., decimate= 500)

    w2=OscilloscopeDigital(stream = dev.streams[0])
    w2.show()
    w2.set_params(xsize = 30, mode = 'scroll', decimate= 500, auto_decimate = True)
    

    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()



if __name__ == '__main__':
    test1()
