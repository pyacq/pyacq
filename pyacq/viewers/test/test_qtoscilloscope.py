import pytest

from pyacq.viewers.qoscilloscope  import QOscilloscope
from pyacq.devices import NumpyDeviceBuffer
import numpy as np

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

nb_channel = 7
sampling_rate = 10000.
chunksize = 250

def test_qoscilloscope():
    app = pg.mkQApp()
    
    length = int(sampling_rate*20)
    t = np.arange(length)/sampling_rate
    buffer = np.random.rand(length, nb_channel)*.00
    buffer += np.sin(2*np.pi*1.2*t)[:,None]*.5
    buffer = buffer.astype('float32')

    dev =NumpyDeviceBuffer()
    dev.configure( nb_channel = 7, sample_interval = 1./sampling_rate, chunksize = chunksize,
                    buffer = buffer)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfermode = 'plaindata')
    dev.initialize()

    
    viewer = QOscilloscope()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()


    def terminate():
        viewer.stop()
        #~ dev.stop()
        viewer.close()
        #~ dev.close()
        app.quit()
    
    dev.start()
    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 10000)
    timer.timeout.connect(terminate)
    timer.start()    
    
    app.exec_()
    

if __name__ == '__main__':
    test_qoscilloscope()