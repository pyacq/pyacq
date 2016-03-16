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



stream_spec = dict(protocol='tcp', interface='127.0.0.1', transfermode='sharedarray',
                        sharedarray_shape=(nb_channel, 2048*50), ring_buffer_method = 'double',
                        dtype = 'float32',)
                        # timeaxis = 1, shape = (nb_channel, -1), 

def test_sosfilter():
    app = pg.mkQApp()
    
                            
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
        filter.stop()
        viewer.stop()
        viewer2.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()


def test_compare_online_offline():
    #~ man = create_manager(auto_close_at_exit=True)
    man = create_manager(auto_close_at_exit=False)
    ng = man.create_nodegroup()

    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer, timeaxis=1,)
    dev.output.configure(**stream_spec)
    dev.initialize()

    coefficients = scipy.signal.iirfilter(7, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    
    filter = ng.create_node('SosFilter')
    filter.configure(coefficients = coefficients)
    filter.input.connect(dev.output)
    filter.output.configure(**stream_spec)
    filter.initialize()
    
    filter.start()
    dev.start()
    
    time.sleep(2.)
    dev.stop()
    time.sleep(.1)
    filter.stop()
    
    
    head = dev.head._get_value()
    output_arr = filter.output.sender._numpyarr._get_value()
    output_arr = output_arr[:, :head]
    
    
    offline_arr =  scipy.signal.sosfilt(coefficients, buffer[:, :head], axis=1, zi=None)
    
    assert np.max(np.abs(output_arr-offline_arr))<1e-6, 'online differt from offline'
    
    from matplotlib import pyplot
    fig, ax = pyplot.subplots()
    ax.plot(output_arr[0,:], color = 'r')
    ax.plot(offline_arr[0,:], color = 'g')
    fig, ax = pyplot.subplots()
    for c in range(nb_channel):
        ax.plot(output_arr[c,:]-offline_arr[c,:], color = 'k')
    pyplot.show()
    
    
    man.close()
    
    
    

if __name__ == '__main__':
    #~ test_sosfilter()
    test_compare_online_offline()

 
