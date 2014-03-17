# -*- coding: utf-8 -*-

from pyacq import (StreamHandler, FakeMultiSignals, FakeDigital, AnaSigSharedMem_to_AnaSigPlainData,
                                        AnaSigPlainData_to_AnaSigSharedMem)
from pyacq.gui import Oscilloscope, OscilloscopeDigital

from pyacq.processing.trigger import AnalogTrigger, DigitalTrigger

import time
from PyQt4 import QtCore,QtGui

import numpy as np

import time

def trigger_analog1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = 32,
                                sampling_rate =1000.,
                                buffer_length = 64,
                                packet_size = 100,
                                last_channel_is_trig = True,
                                )
    dev.initialize()
    dev.start()

    def print_pos(pos):
        print pos
    
    trigger = AnalogTrigger(stream = dev.streams[0],
                                    threshold = 0.25,
                                    front = '+', 
                                    channel = dev.nb_channel-1,
                                    #~ debounce_mode = 'no-debounce',
                                    debounce_mode = 'after-stable',
                                    #~ debounce_mode = 'before-stable',
                                    debounce_time = 0.05,
                                    callbacks = [ print_pos,  ]
                                    )
    

    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = dev.streams[0])
    w1.show()
    visibles = np.ones(dev.nb_channel, dtype = bool)
    visibles[4:] = False
    w1.set_params(xsize = 4.7,
                                    mode = 'scan',
                                visibles = visibles)


    time.sleep(.5)
    w1.auto_gain_and_offset(mode = 2)

    
    app.exec_()
    print 1
    # Stope and release the device
    trigger.stop()
    print 2
    dev.stop()
    print 3
    dev.close()
    print 4



def trigger_digital1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeDigital(streamhandler = streamhandler)
    dev.configure( 
                                nb_channel = 32,
                                sampling_rate =100000.,
                                buffer_length = 60.,
                                packet_size = 100,
                                )
    dev.initialize()
    dev.start()

    def print_pos(pos):
        print pos
    
    trigger = DigitalTrigger(stream = dev.streams[0],
                                    front = '-', 
                                    channel = 0,
                                    #~ debounce_mode = 'no-debounce',
                                    debounce_mode = 'after-stable',
                                    #~ debounce_mode = 'before-stable',
                                    debounce_time = 0.05,
                                    callbacks = [ print_pos,  ]
                                    )

    
    app = QtGui.QApplication([])
    
    w1=OscilloscopeDigital(stream = dev.streams[0])
    w1.show()
    visibles = np.ones(dev.nb_channel, dtype = bool)
    visibles[1:] = False
    w1.set_params(xsize = 4.7,
                                    mode = 'scan',
                                visibles = visibles,
                                refresh_interval = .1)


    time.sleep(.5)
    #~ w1.auto_gain_and_offset(mode = 2)

    
    app.exec_()
    print 1
    # Stope and release the device
    trigger.stop()
    print 2
    dev.stop()
    print 3
    dev.close()
    print 4




if __name__ == '__main__':
    trigger_analog1()
    #~ trigger_digital1()
