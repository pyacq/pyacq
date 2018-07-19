import time
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

from pyacq import create_manager
from pyacq import MeasurementComputing
from pyacq.core.tests.fakenodes import ReceiverWidget
from pyacq.viewers import QOscilloscope, QDigitalOscilloscope

import pytest

#~ import logging
#~ logging.getLogger().level=logging.INFO

@pytest.mark.skip('Need a device for test')
def test_measurementcomputing_infodevice():
    dev = MeasurementComputing()
    for k, v in dev.scan_device_info(0).items():
        print(k, ':', v)
    #~ print(dev.scan_device_info(0))

@pytest.mark.skip('Need a device for test')
def test_measurementcomputing_USB1608_FS_PLUS():

    app = pg.mkQApp()    
    dev = MeasurementComputing()
    

    # ai_channel_index = None
    ai_channel_index = [2, 3, 4 ]
    ai_ranges = (-10, 10)
    
    ai_mode = None
    
    dev.configure(board_num=0, sample_rate=1000, ai_channel_index=ai_channel_index, ai_ranges=ai_ranges, ai_mode=ai_mode)
    dev.outputs['aichannels'].configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
    dev.initialize()
    
    #~ viewer = ReceiverWidget()
    #~ viewer.configure()
    #~ viewer.input.connect(dev.outputs['ai_channel_index'])
    #~ viewer.initialize()
    
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.outputs['aichannels'])
    viewer.initialize()
    viewer.params['scale_mode'] = 'by_channel'
    viewer.params['xsize'] = 5
    viewer.params['refresh_interval'] = 100

    
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
    #~ timer.start()
    
    app.exec_()

@pytest.mark.skip('Need a device for test')
def test_measurementcomputing_USB2533():

    app = pg.mkQApp()    
    dev = MeasurementComputing()
    
    # ai_channel_index = None
    ai_channel_index = [0, 10, 47, ]
    ai_ranges = (-10, 10)
    #~ ai_ranges = (-5, 5)
    #~ ai_ranges = (-1, 1)
    ai_mode = 'single-ended'
    #~ ai_mode = 'differential'  # this should bug whith channel>32
    
    dev.configure(board_num=0, sample_rate=10000., ai_channel_index=ai_channel_index, ai_ranges=ai_ranges, ai_mode=ai_mode)
    dev.outputs['aichannels'].configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.outputs['dichannels'].configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()
    
    viewer0 = QOscilloscope()
    viewer0.configure()
    viewer0.input.connect(dev.outputs['aichannels'])
    viewer0.initialize()
    viewer0.params['scale_mode'] = 'real_scale'
    viewer0.params['xsize'] = 5
    viewer0.params['ylim_min'] = -1.5
    viewer0.params['ylim_max'] = 1.5
    viewer0.params['refresh_interval'] = 100
    viewer0.params['show_left_axis'] = True
    


    viewer1 = QDigitalOscilloscope()
    viewer1.configure()
    viewer1.input.connect(dev.outputs['dichannels'])
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
    #~ timer.start()
    
    app.exec_()


if __name__ == '__main__':
    #~ test_measurementcomputing_infodevice()
    #~ test_measurementcomputing_USB1608_FS_PLUS()
    test_measurementcomputing_USB2533()

 
