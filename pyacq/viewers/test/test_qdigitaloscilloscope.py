# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from pyacq.devices import NumpyDeviceBuffer
from pyacq.viewers.qdigitaloscilloscope import QDigitalOscilloscope

sample_rate = 10000.
chunksize = int(sample_rate//100)
#~ print(chunksize)
#~ exit()

def test_QDigitalOscilloscope():
    
    app = pg.mkQApp()
    
    length = int(sample_rate*200)
    t = np.arange(length)/sample_rate
    buffer = np.zeros((length, 3), dtype='uint8')
    nb_channel = buffer.shape[1]*8
    for i in range(nb_channel):
        b = i//8
        mask =  1 << i%8
        cycle_size = int((i+1)*sample_rate/2)
        period = np.concatenate([np.zeros(cycle_size, dtype='uint8'), np.ones(cycle_size, dtype='uint8')] * int(1+length/cycle_size/2))[:length]
        buffer[:, b] += period*mask

    #~ print(buffer.shape, buffer.dtype)
    #~ exit()
    
    channel_info = [ {'name': 'di{}'.format(c)} for c in range(nb_channel) ]
    
    dev =NumpyDeviceBuffer()
    dev.configure(nb_channel=buffer.shape[1], sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    # hack for channel names
    dev.output.params['channel_info'] = channel_info
    dev.initialize()

    
    viewer = QDigitalOscilloscope()
    #~ viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()

    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()
    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=2000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()


if __name__ =='__main__':
    test_QDigitalOscilloscope()
