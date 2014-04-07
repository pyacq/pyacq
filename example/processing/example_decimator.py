# -*- coding: utf-8 -*-

from pyacq import (StreamHandler, FakeMultiSignals, FakeDigital, AnaSigSharedMem_to_AnaSigPlainData,
                                        AnaSigPlainData_to_AnaSigSharedMem)
from pyacq.gui import Oscilloscope, OscilloscopeDigital, TimeFreq

from pyacq.processing import BandPassFilter, SimpleDecimator

import time
from PyQt4 import QtCore,QtGui

import numpy as np
import scipy.signal


import time

def filter_analog1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure(     nb_channel = 2,
                                sampling_rate =10000.,
                                buffer_length = 30.,
                                packet_size = 100,
                                last_channel_is_trig = True,
                                )
    dev.initialize()
    dev.start()
    
    
    filter = BandPassFilter(stream = dev.streams[0],
                                                streamhandler= streamhandler,
                                                autostart = False,
                                                f_start =0.,
                                                f_stop = dev.streams[0].sampling_rate/10./2.,
                                                )
    decimator = SimpleDecimator( filter.out_stream,
                                                streamhandler= streamhandler,
                                                downsampling_factor = 10,
                                                autostart = False,
                                                )
    
    
                                                
    app = QtGui.QApplication([])
    
    filter.start()
    decimator.start()


    visibles = np.ones(dev.nb_channel, dtype = bool)
    visibles[1:] = False
    
    w1=Oscilloscope(stream = dev.streams[0])
    w2=Oscilloscope(stream = filter.out_stream)
    w3=Oscilloscope(stream = decimator.out_stream)

    time.sleep(.5)
    
    
    for w in [w1, w2, w3]:
        w.auto_gain_and_offset(mode = 0)
        w.set_params(xsize = 1.,
                                        mode = 'scan',
                                        visibles = visibles,
                                        ylims = [-5,5]
                                        )
        w.show()
    
    
    
    app.exec_()
    w1.stop()
    w2.stop()
    
    
    dev.stop()

    dev.close()






if __name__ == '__main__':
    filter_analog1()


