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
buffer = np.random.rand(nb_channel, length)*.3
buffer[0,:] = 0
for i in range(1,20):
    buffer[0, (t>i)&(t<i+.4)] = 2.
    if i%3==0:
        #add  rebounce every 3 triggers
        buffer[0, (t>i+.01)&(t<i+0.015)] = 0.
        buffer[0, (t>i+.02)&(t<i+0.025)] = 0.
buffer = buffer.astype('float32')


def setup_nodes():
    #fake analog stream
    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer, timeaxis=1,)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='sharedarray',
                            sharedarray_shape=(nb_channel, 2048*50), ring_buffer_method = 'double', timeaxis = 1,
                            dtype = 'float32')
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


def test_AnalogTrigger_nodebounce():
    app = pg.mkQApp()
    
    dev, trigger = setup_nodes()
    trigger.params['debounce_time'] = 0.1
    trigger.params['debounce_mode'] = 'no-debounce'
    
    all_triggers = []
    def on_new_trigger(pos, indexes):
        #~ print(pos, indexes)
        all_triggers.extend(indexes)
    poller = ThreadPollOutput(trigger.output)
    poller.new_data.connect(on_new_trigger)
    
    poller.start()
    trigger.start()
    dev.start()
    
    
    def terminate():
        dev.stop()
        trigger.stop()
        poller.stop()
        poller.wait()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    assert np.array_equal(all_triggers, [1001, 2001, 3001, 3015, 3025, 4001])



def test_AnalogTrigger_after_stable():
    app = pg.mkQApp()
    
    dev, trigger = setup_nodes()
    trigger.params['debounce_time'] = 0.1
    trigger.params['debounce_mode'] = 'after-stable'
    
    all_triggers = []
    def on_new_trigger(pos, indexes):
        #~ print(pos, indexes)
        all_triggers.extend(indexes)
    poller = ThreadPollOutput(trigger.output)
    poller.new_data.connect(on_new_trigger)
    
    dev.start()
    trigger.start()
    poller.start()
    
    def terminate():
        dev.stop()
        trigger.stop()
        poller.stop()
        poller.wait()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    #~ print(all_triggers)
    assert np.array_equal(all_triggers, [1001, 2001,  3025, 4001])


def test_AnalogTrigger_before_stable():
    app = pg.mkQApp()
    
    dev, trigger = setup_nodes()
    trigger.params['debounce_time'] = 0.1
    trigger.params['debounce_mode'] = 'before-stable'
    
    all_triggers = []
    def on_new_trigger(pos, indexes):
        #~ print(pos, indexes)
        all_triggers.extend(indexes)
    poller = ThreadPollOutput(trigger.output)
    poller.new_data.connect(on_new_trigger)
    
    dev.start()
    trigger.start()
    poller.start()
    
    def terminate():
        dev.stop()
        trigger.stop()
        poller.stop()
        poller.wait()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    #~ print(all_triggers)
    assert np.array_equal(all_triggers, [1001, 2001,  3001, 4001])


if __name__ == '__main__':
    test_AnalogTrigger_nodebounce()
    test_AnalogTrigger_after_stable()
    test_AnalogTrigger_before_stable()

 
