import time
import numpy as np
import pyqtgraph as pg

from pyacq import create_manager, InputStream, NumpyDeviceBuffer, ThreadPollInput
from pyacq.dsp.trigger import AnalogTrigger, DigitalTrigger

from pyqtgraph.Qt import QtCore, QtGui


nb_channel = 6
sample_rate =1000.
chunksize = 100

length = int(sample_rate*20)
t = np.arange(length)/sample_rate
buffer = np.random.rand(nb_channel, length)*.3

for i in range(20):
    buffer[0, (t>i)&(t<i+.2)] = 2.
    if np.random.rand()<.5:
        #add  rebounce
        buffer[0, (t>i+.01)&(t<i+0.015)] = 0.
buffer = buffer.astype('float32')



def test_AnalogTrigger():
    app = pg.mkQApp()
    
    #fake analog stream
    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer, timeaxis=1,)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='sharedarray',
                            sharedarray_shape=(nb_channel, 2048*50), ring_buffer_method = 'double', timeaxis = 1)
    dev.initialize()
    
    # trigger
    trigger = AnalogTrigger()
    trigger.configure()
    trigger.input.connect(dev.output)
    trigger.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    trigger.initialize()
    trigger.params['threshold'] = 1.
    trigger.params['front'] = '+'
    

    def on_new_trigger(pos, index):
        print(pos, index)

    instream = InputStream()
    instream.connect(trigger.output)
    poller = ThreadPollInput(input_stream=instream)
    poller.new_data.connect(on_new_trigger)
    
    dev.start()
    trigger.start()
    poller.start()
    print('started')
    
    def terminate():
        dev.stop()
        trigger.stop()
        poller.stop()
        poller.wait()
        app.quit()
    

    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=20000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    
if __name__ == '__main__':
    test_AnalogTrigger()

 
