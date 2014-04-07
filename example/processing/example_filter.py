# -*- coding: utf-8 -*-

from pyacq import (StreamHandler, FakeMultiSignals, FakeDigital, AnaSigSharedMem_to_AnaSigPlainData,
                                        AnaSigPlainData_to_AnaSigSharedMem)
from pyacq.gui import Oscilloscope, OscilloscopeDigital, TimeFreq

from pyacq.processing import BandPassFilter

import time
from PyQt4 import QtCore,QtGui

import numpy as np
import scipy.signal


import time

def filter_analog1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = 64,
                                sampling_rate =10000.,
                                buffer_length = 30.,
                                packet_size = 100,
                                last_channel_is_trig = True,
                                )
    dev.initialize()
    dev.start()

    
    filter = BandPassFilter(stream = dev.streams[0],
                                                streamhandler= streamhandler,
                                                autostart = False)
    app = QtGui.QApplication([])
    
    filter.start()

    time.sleep(.2)
    filter.set_params(f_start = 300., f_stop =np.inf)
    time.sleep(.2)
    filter.set_params(f_start = 0., f_stop =40.3)
    time.sleep(.2)
    filter.set_params(f_start = 30., f_stop =70.)


    visibles = np.ones(dev.nb_channel, dtype = bool)
    visibles[1:] = False
    
    w1=Oscilloscope(stream = dev.streams[0])
    w2=Oscilloscope(stream = filter.out_stream)

    time.sleep(.5)
    
    
    for w in [w1, w2]:
        w.auto_gain_and_offset(mode = 0)
        w.set_params(xsize = 1.,
                                        mode = 'scan',
                                        visibles = visibles,
                                        ylims = [-5,5]
                                        )
        w.show()
    
    #~ w3=TimeFreq(stream = dev.streams[0])
    #~ w4=TimeFreq(stream = filter.out_stream)
    #~ for w in [w3, w4]:
        #~ w.set_params(colormap = 'hot', visibles = visibles, 
                                            #~ xsize=30, 
                                            #~ nb_column = 1)
        #~ w.show()
    
    
    
    app.exec_()
    w1.stop()
    w2.stop()
    
    
    dev.stop()

    dev.close()






if __name__ == '__main__':
    filter_analog1()


