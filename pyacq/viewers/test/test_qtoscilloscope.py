import pytest

from pyacq.viewers.qoscilloscope  import QOscilloscope
from pyacq.devices import NumpyDeviceBuffer
import numpy as np

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

nb_channel = 7

def test_qoscilloscope():
    app = pg.mkQApp()

    dev =NumpyDeviceBuffer()
    dev.configure( nb_channel = 7, sample_interval = 0.001)
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '*',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1,nb_channel), compression ='',
                        scale = None, offset = None, units = '' )
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
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