import pytest

from pyacq import create_manager
from pyacq.viewers.qoscilloscope  import QOscilloscope
from pyacq.devices import NumpyDeviceBuffer
import numpy as np

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

nb_channel = 32
sampling_rate = 10000.
chunksize = 100

def test_qoscilloscope():
    
    man = create_manager(auto_close_at_exit = False)
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

    
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog = True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    viewer.params['decimation_method'] = 'min_max'


    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()
    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 2000)
    timer.timeout.connect(terminate)
    #~ timer.start()
    
    app.exec_()

    man.close()


  

if __name__ == '__main__':
    test_qoscilloscope()