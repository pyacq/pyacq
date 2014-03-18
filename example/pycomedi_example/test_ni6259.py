# -*- coding: utf-8 -*-
"""
Attention :  
  * sous ubuntu il faut lancer comedi_soft_calibrate
  * le path de comedi_soft_calibrate n'est pas clui d'unbutu
  donc on s'en sort avec ça:
  sudo mkdir /var/lib/libcomedi0
  sudo comedi_soft_calibrate /dev/comedi0

  

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
                                sampling_rate =20000.,
                                buffer_length = 5.,
                            )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    #w1.auto_gain_and_offset(mode = 0)
    visibles = np.zeros(dev.nb_channel, dtype = bool)
    visibles[21] = True
    w1.set_params(xsize = 3.7, refresh_interval = 100, 
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
