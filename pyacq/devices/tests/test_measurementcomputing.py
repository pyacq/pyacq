import time
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

from pyacq import create_manager
from pyacq import MeasurementComputing
#~ from pyacq.core.tests.fakenodes import ReceiverWidget
from pyacq.viewers import QOscilloscope

#~ import logging
#~ logging.getLogger().level=logging.INFO


def test_measurementcomputing_infodevice():
    dev = MeasurementComputing()
    for k, v in dev.scan_device_info(0).items():
        print(k, ':', v)
    #~ print(dev.scan_device_info(0))


def test_measurementcomputing_USB1608_FS_PLUS():

    app = pg.mkQApp()    
    dev = MeasurementComputing()
    
    dev.configure(board_num = 0, sampling_rate = 1000.5)
    dev.outputs['signals'].configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()
    
    #~ return
    
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.outputs['signals'])
    viewer.initialize()
    #~ viewer.params['scale_mode'] = 'by_channel'
    #~ viewer.params['xsize'] = 1
    #~ viewer.params['refresh_interval'] = 100

    
    dev.start()
    viewer.start()
    viewer.show()
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 10000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()


def test_measurementcomputing_USB2533():

    app = pg.mkQApp()    
    dev = MeasurementComputing()
    
    dev.configure(board_num = 1, sampling_rate = 10000., timer_interval = 50)
    dev.outputs['signals'].configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.outputs['digital'].configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()
    
    viewer0 = ReceiverWidget()
    viewer0.configure()
    viewer0.input.connect(dev.outputs['signals'])
    viewer0.initialize()

    viewer1 = ReceiverWidget()
    viewer1.configure()
    viewer1.input.connect(dev.outputs['digital'])
    viewer1.initialize()
    
    dev.start()
    viewer0.start()
    viewer0.show()

    viewer1.start()
    viewer1.show()
    
    def terminate():
        viewer0.stop()
        viewer1.stop()
        dev.stop()
        viewer0.close()
        viewer1.close()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 10000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()


if __name__ == '__main__':
    #~ test_measurementcomputing_infodevice()
    test_measurementcomputing_USB1608_FS_PLUS()
    #~ test_measurementcomputing_USB2533()

 
