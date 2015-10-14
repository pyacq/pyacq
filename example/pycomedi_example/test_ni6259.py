# -*- coding: utf-8 -*-
"""
Attention :  
  * sous ubuntu il faut lancer sudo comedi_soft_calibrate (avec la derniere version (calibrate3)
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
    
    channel_selection = np.array([True]*32, dtype = bool)
    #~ channel_selection[22:] = False
    channel_selection[[22,23, ]] = False
    
    channel_selection = channel_selection.tolist()
    n = 32
    print 'N', np.sum(channel_selection)
    streamhandler = StreamHandler()
    
    
    # Configure and start
    dev = ComediMultiSignals(streamhandler = streamhandler)
    dev.configure( device_path = '/dev/comedi0',
                                sampling_rate =54000.,
                                buffer_length =60.,
                                
                                subdevices = [
                                    {
                                        'type' : 'AnalogInput',
                                        'nb_channel' : 32,
                                        'params' :{  }, 
                                        'by_channel_params' : { 
                                                                'channel_indexes' : range(n),
                                                                'channel_names' : [ 'AI Channel {}'.format(i) for i in range(n)],
                                                                'channel_selection' : channel_selection,
                                                                'channel_ranges' : [ [-10., 10.] for i in range(n) ],
                                                                }
                                        },                                

                                ]
                                
                            )
    dev.initialize()
    dev.start()
    
    app = QtGui.QApplication([])
    w1=Oscilloscope(stream = dev.streams[0])
    #w1.auto_gain_and_offset(mode = 0)
    visibles = np.zeros(dev.nb_channel, dtype = bool)
    visibles[-1] = True
    w1.set_params(xsize = 40., refresh_interval = 100, 
                                mode = 'scan', ylims = [-1.5, 1.5],
                                visibles = visibles,
                                gains = np.ones(dev.nb_channel),
                                offsets = np.zeros(dev.nb_channel),
                                )
    w1.show()
    
    app.exec_()
    
    dev.stop()
    dev.close()
    w1.stop()



if __name__ == '__main__':
    test1()
