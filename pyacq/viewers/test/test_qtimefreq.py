import pytest
import logging

from pyacq import create_manager, ThreadPollInput
from pyacq.viewers.qtimefreq import TimeFreqWorker, QTimeFreq, HAVE_SCIPY, generate_wavelet_fourier
from pyacq.devices import NumpyDeviceBuffer
import numpy as np
import time

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg


logger = logging.getLogger()

nb_channel = 8
sample_rate = 1000.
chunksize = 50

#~ nb_channel = 32
#~ sample_rate = 20000
#~ chunksize = 100

# some moving sinus
length = int(sample_rate*20)
times = np.arange(length)/sample_rate
buffer = np.random.rand(length, nb_channel)
f1, f2, speed = 20., 60., .05
freqs = (np.sin(np.pi*2*speed*times)+1)/2 * (f2-f1) + f1
phases = np.cumsum(freqs/sample_rate)*2*np.pi
ampl = np.abs(np.sin(np.pi*2*speed*8*times))*.8
buffer += (np.sin(phases)*ampl)[:,None]
buffer = buffer.astype('float32')


@pytest.mark.skipif(not HAVE_SCIPY, reason='no HAVE_SCIPY')
def test_TimeFreqWorker():
    # test only one worker
    man = create_manager(auto_close_at_exit=False)
    #~ man = create_manager(auto_close_at_exit = True)
    
    ng = man.create_nodegroup()

    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer.transpose(), timeaxis=1,)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='sharedarray',
                            sharedarray_shape=(nb_channel, 2048*50), ring_buffer_method = 'double')
    dev.initialize()
    
    workers = []
    for i in range(nb_channel):
        worker = ng.create_node('TimeFreqWorker')
        worker.configure(max_xsize=30., channel=i, local=False)
        worker.input.connect(dev.output)
        worker.output.configure()
        worker.initialize()
        workers.append(worker)
    
    # compute wavelet : 3 s. of signal at 500Hz
    import scipy.signal
    xsize, wf_size, sub_sr= 3., 2048, 500.
    wavelet_fourrier = generate_wavelet_fourier(wf_size, 1., 100., 2.5, sub_sr, 2.5, 0)
    filter_b = scipy.signal.firwin(9, 1. / 20., window='hamming')
    filter_a = np.array([1.])
    
    dev.start()
    
    time.sleep(.5)
    for worker in workers:
        worker.start()
    
    # change the wavelet on fly
    for worker in workers:
        worker.on_fly_change_wavelet(wavelet_fourrier=wavelet_fourrier, downsample_factor=20,
            sig_chunk_size=2048*20,
            plot_length=int(sub_sr*xsize), filter_a=filter_a, filter_b=filter_b)
    
    head = 0
    for i in range(4):
        time.sleep(.5)
        head += int(sample_rate*.5)
        for worker in workers:
            worker.compute_one_map(head)
    
    dev.stop()
    
    man.close()



@pytest.mark.skipif(not HAVE_SCIPY, reason='no HAVE_SCIPY')
def test_qtimefreq_local_worker():
    
    #~ man = create_manager(auto_close_at_exit = True)
    man = create_manager(auto_close_at_exit=False)
    ng = man.create_nodegroup()
    
    app = pg.mkQApp()
    
    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    dev.initialize()
    
    
    
    viewer = QTimeFreq()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    viewer.params['nb_column'] = 4
    viewer.params['refresh_interval'] = 1000
    
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()

    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    man.close()


@pytest.mark.skipif(not HAVE_SCIPY, reason='no HAVE_SCIPY')
def test_qtimefreq_distributed_worker():
    #logger.level = logging.DEBUG
    man = create_manager(auto_close_at_exit=False)

    nodegroup_friends = [man.create_nodegroup() for _ in range(4)]
    
    app = pg.mkQApp()

    ng = man.create_nodegroup()
    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    dev.initialize()
    
    viewer = QTimeFreq()
    viewer.configure(with_user_dialog=True, nodegroup_friends=nodegroup_friends)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    viewer.params['nb_column'] = 4
    viewer.params['refresh_interval'] = 1000


    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()

    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    man.close()



if __name__ == '__main__':
    test_TimeFreqWorker()
    test_qtimefreq_local_worker()
    test_qtimefreq_distributed_worker()


