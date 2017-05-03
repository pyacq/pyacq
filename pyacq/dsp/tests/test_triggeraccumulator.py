# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time
import numpy as np
import pyqtgraph as pg

from pyacq import create_manager, InputStream, NumpyDeviceBuffer, ThreadPollOutput
from pyacq.dsp.trigger import AnalogTrigger, DigitalTrigger
from pyacq.dsp.triggeraccumulator import TriggerAccumulator


from pyqtgraph.Qt import QtCore, QtGui



nb_channel = 2
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



def test_TriggerAccumulator():
    app = pg.mkQApp()
    
    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata', dtype='float32')
    dev.initialize()

    trigger = AnalogTrigger()
    trigger.configure()
    trigger.input.connect(dev.output)
    trigger.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    trigger.initialize()
    trigger.params['threshold'] = 1.
    trigger.params['debounce_mode'] = 'no-debounce'
    trigger.params['front'] = '+'
    trigger.params['debounce_time'] = 0.1
    
    triggeraccumulator = TriggerAccumulator()
    triggeraccumulator.configure(max_stack_size = 5)
    triggeraccumulator.inputs['signals'].connect(dev.output)
    triggeraccumulator.inputs['events'].connect(trigger.output)
    triggeraccumulator.initialize()
    triggeraccumulator.params['stack_size'] = 3
    triggeraccumulator.params['left_sweep'] = -.2
    triggeraccumulator.params['right_sweep'] = .5
    
    #~ def on_new_chunk(total_trig):
        #~ print
        #~ print('total_trig', total_trig)
        #~ print('triggeraccumulator.stack', triggeraccumulator.stack)
        #~ print('triggeraccumulator.total_trig', triggeraccumulator.total_trig)
    #~ triggeraccumulator.new_chunk.connect(on_new_chunk)
    
    dev.start()
    trigger.start()
    triggeraccumulator.start()
    
    
    
    def terminate():
        dev.stop()
        trigger.stop()
        triggeraccumulator.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    assert triggeraccumulator.total_trig==6


if __name__ == '__main__':
    test_TriggerAccumulator()

