# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from pyacq.devices import NumpyDeviceBuffer
from pyacq.viewers.qoscilloscope import QOscilloscope
from pyacq.viewers.qtriggeredoscilloscope import QTriggeredOscilloscope

nb_channel = 6
sample_rate =1000.
chunksize = 100

length = int(sample_rate*20)
t = np.arange(length)/sample_rate
buffer = np.random.rand(length, nb_channel)*.3
buffer[:, 0] = 0
for i in range(1,20):
    buffer[(t>i)&(t<i+.4), 0] = 2.
    if i%3==0:
        #add  rebounce every 3 triggers
        buffer[(t>i+.01)&(t<i+0.015), 0] = 0.
        buffer[(t>i+.02)&(t<i+0.025), 0] = 0.
buffer = buffer.astype('float32')


def test_QTriggeredOscilloscope():
    app = pg.mkQApp()
    
    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata', dtype='float32')
    dev.initialize()
    
    viewer = QTriggeredOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()

    viewer.trigger.params['threshold'] = 1.
    viewer.trigger.params['debounce_mode'] = 'after-stable'
    viewer.trigger.params['front'] = '+'
    viewer.trigger.params['debounce_time'] = 0.1
    viewer.triggeraccumulator.params['stack_size'] = 3
    viewer.triggeraccumulator.params['left_sweep'] = -.2
    viewer.triggeraccumulator.params['right_sweep'] = .5
    
    viewer2 = QOscilloscope()
    viewer2.configure(with_user_dialog=True)
    viewer2.input.connect(dev.output)
    viewer2.initialize()
    viewer2.show()

    def terminate():
        viewer.stop()
        viewer2.stop()
        dev.stop()
        viewer.close()
        viewer2.close()
        dev.close()
        app.quit()
    
    dev.start()
    viewer.start()
    viewer2.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=2000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()


if __name__ == '__main__':
    test_QTriggeredOscilloscope()
