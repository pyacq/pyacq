import pytest

from pyacq import create_manager
from pyacq.viewers.qtimefreq  import TimeFreqCompute, QTimeFreq, HAVE_SCIPY, generate_wavelet_fourier
from pyacq.devices import NumpyDeviceBuffer
import numpy as np
import time

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

nb_channel = 32
sampling_rate = 20000
#~ sampling_rate = 500.
chunksize = 100

length = int(sampling_rate*20)
t = np.arange(length)/sampling_rate
buffer = np.random.rand(length, nb_channel)*.3
buffer += np.sin(2*np.pi*1.2*t)[:,None]*.5
buffer = buffer.astype('float32')

@pytest.mark.skipif(not HAVE_SCIPY, reason = 'no HAVE_SCIPY')
def test_TimeFreqCompute():
    # test only one worker
    man = create_manager(auto_close_at_exit = True)
    ng = man.create_nodegroup()

    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure( nb_channel = nb_channel, sample_interval = 1./sampling_rate, chunksize = chunksize,
                    buffer = buffer.transpose(), timeaxis=1,)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfermode = 'sharedarray',
                            sharedarray_shape = (nb_channel, 2048*50), ring_buffer_method = 'double')
    dev.initialize()
    print(dev.output.params)
    worker = ng.create_node('TimeFreqCompute')
    worker.configure(max_xsize = 30., channel=0)
    worker.input.connect(dev.output)
    worker.output.configure()
    worker.initialize()
    
    # compute wavelet : 3 s. of signal at 500Hz
    import scipy.signal
    xsize, wf_size,  sub_sr= 3., 2048, 500.
    wavelet_fourrier = generate_wavelet_fourier(wf_size, 1., 100., 2.5, sub_sr, 2.5, 0)
    filter_b = scipy.signal.firwin(9, 1. / 20., window='hamming')
    filter_a = np.array([1.])
    
    dev.start()
    worker.start()
    
    time.sleep(.5)
    
    #change the wavelet on fly
    worker.on_fly_change_wavelet(wavelet_fourrier=wavelet_fourrier, downsampling_factor=20,
            sig_chunk_size = 2048*20,
            plot_length=int(sub_sr*xsize), filter_a=filter_a, filter_b=filter_b)
    
    time.sleep(2.)
    
    dev.stop()
    worker.stop()
    
    #~ man.close()

@pytest.mark.skipif(not HAVE_SCIPY, reason = 'no HAVE_SCIPY')
def test_qtimefreq_simple():
    
    man = create_manager(auto_close_at_exit = True)
    ng = man.create_nodegroup()
    
    app = pg.mkQApp()
    
    length = int(sampling_rate*20)
    t = np.arange(length)/sampling_rate
    buffer = np.random.rand(length, nb_channel)*.3
    buffer += np.sin(2*np.pi*1.2*t)[:,None]*.5
    buffer = buffer.astype('float32')

    #~ dev =NumpyDeviceBuffer()
    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure( nb_channel = nb_channel, sample_interval = 1./sampling_rate, chunksize = chunksize,
                    buffer = buffer)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfermode = 'plaindata')
    dev.initialize()
    
    
    viewer = QTimeFreq()
    viewer.configure(with_user_dialog = True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    viewer.params['nb_column'] = 8
    viewer.params['refresh_interval'] = 2000
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()

    viewer.start()
    
    # start for a while
    #~ timer = QtCore.QTimer(singleShot = True, interval = 2000)
    #~ timer.timeout.connect(terminate)
    #~ timer.start()
    
    app.exec_()

    #~ man.close()


@pytest.mark.skipif(not HAVE_SCIPY, reason = 'no HAVE_SCIPY')
def test_stimefreq_distributed():
    man = create_manager(auto_close_at_exit = True)
    ng = man.create_nodegroup()

    #~ host = man.connect_host('neuro-090', 'tcp://neuro-090:240611')
    #~ nodegroup_friends = [host.create_nodegroup() for _ in range(4)]
    
    nodegroup_friends = [man.create_nodegroup() for _ in range(4)]
    
    
    app = pg.mkQApp()
    
    length = int(sampling_rate*20)
    t = np.arange(length)/sampling_rate
    buffer = np.random.rand(length, nb_channel)*.3
    buffer += np.sin(2*np.pi*1.2*t)[:,None]*.5
    buffer = buffer.astype('float32')

    #~ dev =NumpyDeviceBuffer()
    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure( nb_channel = nb_channel, sample_interval = 1./sampling_rate, chunksize = chunksize,
                    buffer = buffer)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfermode = 'plaindata')
    dev.initialize()
    
    
    
    viewer = QTimeFreq()
    viewer.configure(with_user_dialog = True, nodegroup_friends=nodegroup_friends)
    #~ viewer.configure(with_user_dialog = True, nodegroup_friends =None)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    viewer.params['nb_column'] = 4
    viewer.params['refresh_interval'] = 2000


    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()

    viewer.start()
    
    # start for a while
    #~ timer = QtCore.QTimer(singleShot = True, interval = 2000)
    #~ timer.timeout.connect(terminate)
    #~ timer.start()
    
    app.exec_()

    #~ man.close()
    



if __name__ == '__main__':
    #~ test_TimeFreqCompute()
    #~ test_qtimefreq_simple()
    test_stimefreq_distributed()

