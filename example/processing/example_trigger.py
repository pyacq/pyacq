# -*- coding: utf-8 -*-

from pyacq import (StreamHandler, FakeMultiSignals, AnaSigSharedMem_to_AnaSigPlainData,
                                        AnaSigPlainData_to_AnaSigSharedMem)
from pyacq.gui import Oscilloscope

from pyacq.processing.trigger import AnalogTrigger

import time
from PyQt4 import QtCore,QtGui

import numpy as np

import time

def trigger_analog1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = 16,
                                sampling_rate =1000.,
                                buffer_length = 64,
                                packet_size = 100,
                                last_channel_is_trig = True,
                                )
    dev.initialize()
    dev.start()

    
    trigger = AnalogTrigger(stream = dev.streams[0],
                                    threshold = 0.25,
                                    front = '+', 
                                    channel = dev.nb_channel-1,
                                    #~ debounce_mode = 'no-debounce',
                                    #~ debounce_mode = 'after-stable',
                                    debounce_mode = 'before-stable',
                                    debounce_time = 0.05,
                                    
                                    )
    

    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = dev.streams[0])
    w1.show()
    visibles = np.ones(16, dtype = bool)
    visibles[4:] = False
    w1.set_params(xsize = 3.,
                                    mode = 'scan',
                                visibles = visibles)


    time.sleep(.5)
    w1.auto_gain_and_offset(mode = 2)

    
    app.exec_()
    
    # Stope and release the device
    dev.stop()
    dev.close()






if __name__ == '__main__':
    trigger_analog1()