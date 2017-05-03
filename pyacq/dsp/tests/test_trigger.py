# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time
import numpy as np
import pyqtgraph as pg

from pyacq import create_manager, InputStream, NumpyDeviceBuffer, ThreadPollOutput
from pyacq.dsp.trigger import AnalogTrigger, DigitalTrigger

from pyqtgraph.Qt import QtCore, QtGui

nb_channel = 6
sample_rate =1000.
chunksize = 100

length = int(sample_rate*20)
t = np.arange(length)/sample_rate
buffer = np.random.rand(length, nb_channel)*.3
buffer[:, 0] = 0
for i in range(1,5):
    buffer[(t>i)&(t<i+.4), 0] = 2.
    if i%3==0:
        #add  rebounce every 3 triggers
        buffer[(t>i+.01)&(t<i+0.015), 0] = 0.
        buffer[(t>i+.02)&(t<i+0.025), 0] = 0.
buffer = buffer.astype('float32')


def setup_nodes():
    #fake analog stream

    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata', dtype='float32')
    dev.initialize()

    # trigger
    trigger = AnalogTrigger()
    trigger.configure()
    trigger.input.connect(dev.output)
    trigger.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    trigger.initialize()
    trigger.params['threshold'] = 1.
    trigger.params['front'] = '+'
    
    return dev, trigger


def check_trigger(debounce_time, debounce_mode, targeted_trigs, detected_triggers):
    app = pg.mkQApp()
    
    dev, trigger = setup_nodes()
    trigger.params['debounce_time'] = debounce_time
    trigger.params['debounce_mode'] = debounce_mode
    
    def on_new_trigger(pos, indexes):
        #~ print(pos, indexes)
        detected_triggers.extend(indexes)
    poller = ThreadPollOutput(trigger.output, return_data=True)
    poller.new_data.connect(on_new_trigger)
    
    poller.start()
    trigger.start()
    dev.start()
    
    
    def terminate():
        dev.stop()
        trigger.stop()
        poller.stop()
        poller.wait()
        assert np.array_equal(detected_triggers, targeted_trigs), '{} should be {}'.format(detected_triggers, targeted_trigs)    
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    
    

def test_AnalogTrigger_nodebounce():
    targeted_trigs = [1001, 2001, 3001, 3015, 3025, 4001]
    check_trigger(0.1, 'no-debounce', targeted_trigs, [])


def test_AnalogTrigger_after_stable():
    targeted_trigs = [1001, 2001,  3025, 4001]
    check_trigger(0.1,  'after-stable', targeted_trigs, [])

def test_AnalogTrigger_before_stable():
    targeted_trigs = [1001, 2001,  3001, 4001]
    check_trigger(0.1,  'before-stable', targeted_trigs, [])
    
if __name__ == '__main__':
    test_AnalogTrigger_nodebounce()
    test_AnalogTrigger_after_stable()
    test_AnalogTrigger_before_stable()

 
