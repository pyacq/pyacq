# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import pytest

from pyacq import create_manager
from pyacq.viewers.qoscilloscope import QOscilloscope
from pyacq.viewers.qdigitaloscilloscope import QDigitalOscilloscope
from pyacq.devices import NumpyDeviceBuffer
import numpy as np

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg


sample_rate = 1000.
chunksize = 20


def test_QDigitalOscilloscope():
    
    app = pg.mkQApp()
    
    length = int(sample_rate*20)
    t = np.arange(length)/sample_rate
    buffer = np.zeros((length, 3), dtype='uint8')
    nb_channel = buffer.shape[1]*8
    for i in range(nb_channel):
        b = i//8
        mask =  1 << i%8
        cycle_size = int((i+1)*sample_rate/2)
        period = np.concatenate([np.ones(cycle_size, dtype='uint8'), np.zeros(cycle_size, dtype='uint8')] * int(1+length/cycle_size/2))[:length]
        buffer[:, b] += period*mask


    dev =NumpyDeviceBuffer()
    dev.configure(nb_channel=buffer.shape[1], sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
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
    #~ timer.start()
    
    app.exec_()


if __name__ =='__main__':
    test_QDigitalOscilloscope()
