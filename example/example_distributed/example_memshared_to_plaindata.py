# -*- coding: utf-8 -*-

from pyacq import (StreamHandler, FakeMultiSignals, AnaSigSharedMem_to_AnaSigPlainData,
                                        AnaSigPlainData_to_AnaSigSharedMem)
from pyacq.gui import Oscilloscope

import time

from PyQt4 import QtCore,QtGui

import numpy as np

import multiprocessing as mp


info_port = 2000


def on_pc1():
    streamhandler = StreamHandler()
    
    # Configure and start
    dev = FakeMultiSignals(streamhandler = streamhandler)
    dev.configure( #name = 'Test dev',
                                nb_channel = 16,
                                sampling_rate =1000.,
                                buffer_length = 64,
                                packet_size = 100,
                                )
    dev.initialize()
    dev.start()
    
    
    channel_mask = np.ones(16, dtype = bool)
    channel_mask[::2] = False
    converter1 = AnaSigSharedMem_to_AnaSigPlainData(streamhandler, dev.streams[0],
                                                                                                    info_port = info_port, 
                                                                                                    compress = 'blosc',
                                                                                                    channel_mask = channel_mask,
                                                                                                    )
    time.sleep(20.)
    
    converter1.stop()
    
    dev.stop()
    dev.close()    
    


def on_pc2():
    streamhandler = StreamHandler()
    
    converter2 = AnaSigPlainData_to_AnaSigSharedMem(streamhandler, "tcp://localhost:{}".format(info_port),
                                                                buffer_length = 20., timeout_reconnect = .5)
    
    app = QtGui.QApplication([])
    
    w1=Oscilloscope(stream = converter2.sharedmem_stream)
    w1.show()
    
    w1.auto_gain_and_offset(mode = 1)
    w1.change_param_global(xsize = 5., mode = 'scan')

    app.exec_()


    



if __name__ == '__main__':
        
    p1 = mp.Process(target = on_pc1)
    p1.start()
    time.sleep(.5)
    
    p2 = mp.Process(target = on_pc2)
    p2.start()
    
    
    p1.join()
    time.sleep(5.)
    print 'restart one'
    p1 = mp.Process(target = on_pc1)
    p1.start()
    p1.join()




