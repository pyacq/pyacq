import time
import numpy as np
import pyqtgraph as pg

from pyacq import create_manager, InputStream, NumpyDeviceBuffer, ThreadPollOutput
from pyacq.dsp.sosfilter import SosFilter
from pyacq.viewers.qoscilloscope import QOscilloscope

from pyqtgraph.Qt import QtCore, QtGui
import scipy.signal


nb_channel = 8
sample_rate =1000.
chunksize = 100


length = int(sample_rate*20)
times = np.arange(length)/sample_rate
buffer = np.random.rand(nb_channel, length) *.3
f1, f2, speed = 20., 60., .05
freqs = (np.sin(np.pi*2*speed*times)+1)/2 * (f2-f1) + f1
phases = np.cumsum(freqs/sample_rate)*2*np.pi
ampl = np.abs(np.sin(np.pi*2*speed*8*times))*.8
buffer += (np.sin(phases)*ampl)[None, :]
buffer = buffer.astype('float32')




def test_sosfilter():
    app = pg.mkQApp()
    
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', transfermode='sharedarray',
                            sharedarray_shape=(nb_channel, 2048*50), ring_buffer_method = 'double', timeaxis = 1,
                            dtype = 'float32', shape = (nb_channel, -1), )
                            
    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer, timeaxis=1,)
    dev.output.configure(**stream_spec)
    dev.initialize()
    
    
    f1, f2 = 40., 60.
    
    coefficients = scipy.signal.iirfilter(7, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    
    filter = SosFilter()
    filter.configure(coefficients = coefficients)
    filter.input.connect(dev.output)
    filter.output.configure(**stream_spec)
    filter.initialize()
    
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(filter.output)
    viewer.initialize()
    viewer.show()

    viewer2 = QOscilloscope()
    viewer2.configure(with_user_dialog=True)
    viewer2.input.connect(dev.output)
    viewer2.initialize()
    viewer2.show()
    
    viewer2.start()
    viewer.start()
    filter.start()
    dev.start()
    
    
    def terminate():
        dev.stop()
        trigger.stop()
        viewer.stop()
        viewer2.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    #~ timer.start()
    
    app.exec_()

if __name__ == '__main__':
    test_sosfilter()

 
