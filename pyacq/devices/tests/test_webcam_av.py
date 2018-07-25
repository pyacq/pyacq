# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time

from pyacq import create_manager
from pyacq.devices.webcam_av import WebCamAV, HAVE_AV, get_device_list_dshow
from pyacq.viewers.imageviewer import ImageViewer

from pyqtgraph.Qt import QtCore, QtGui

import pytest

@pytest.mark.skip(reason="need Device")
@pytest.mark.skipif(not HAVE_AV, reason='no have av')
def test_webcam_opencv():
    # in main App
    app = QtGui.QApplication([])
    
    dev = WebCamAV(name='cam')
    dev.configure(camera_num=0)
    dev.output.configure(protocol='tcp', interface='127.0.0.1',transfermode='plaindata',)
    dev.initialize()
    print(dev.output.params)
    
    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    #~ timer.start()
    app.exec_()

def test_get_device_list_dshow():
    device_names = get_device_list_dshow()
    print(device_names)

if __name__ == '__main__':
    test_webcam_opencv()
    
    #~ test_get_device_list_dshow()
    
