# -*- coding: utf-8 -*-

from pyacq import (StreamHandler, FakeMultiSignals, FakeDigital, AnaSigSharedMem_to_AnaSigPlainData,
                                        AnaSigPlainData_to_AnaSigSharedMem)
from pyacq.gui import Oscilloscope, OscilloscopeDigital

from pyacq.processing import AnalogTrigger, StackedChunkOnTrigger

import time
from PyQt4 import QtCore,QtGui

import numpy as np

import time

def test1():
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
    
    def print_new_chunk(n):
        print 'new stackedchunk', n

    stackedchunk = StackedChunkOnTrigger(stream = dev.streams[0],
                                                                                stack_size = 20,
                                                                                left_sweep = 0.1,
                                                                                right_sweep = 0.1,
                                                                                )
    stackedchunk.new_chunk.connect(print_new_chunk)
    
    trigger = AnalogTrigger(stream = dev.streams[0],
                                    threshold = 0.25,
                                    front = '+', 
                                    channel = dev.nb_channel-1,
                                    #~ debounce_mode = 'no-debounce',
                                    debounce_mode = 'after-stable',
                                    #~ debounce_mode = 'before-stable',
                                    debounce_time = 0.05,
                                    callbacks = [ print_pos,  stackedchunk.on_trigger]
                                    )
    

    
    app = QtGui.QApplication([])
    
    
    time.sleep(.5)

    
    app.exec_()
    # Stope and release the device
    trigger.stop()
    dev.stop()
    dev.close()




if __name__ == '__main__':
    test1()
