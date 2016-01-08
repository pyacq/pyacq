# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time

from pyacq import create_manager
from pyacq.devices.webcam_imageio import WebCamImageIO, HAVE_IMAGEIO
from pyacq.viewers.imageviewer import ImageViewer

from pyqtgraph.Qt import QtCore, QtGui

import pytest


@pytest.mark.skipif(not HAVE_IMAGEIO, reason='no have imageio')
def test_webcam_imageio():
    # in main App
    app = QtGui.QApplication([])
    
    dev = WebCamImageIO(name='cam0')
    dev.configure(camera_num=0)
    dev.output.configure(protocol='tcp', interface='127.0.0.1',transfertmode='plaindata',)
    dev.initialize()
    
    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()
    
    def terminate():
        dev.stop()
        dev.close()
        viewer.stop()
        viewer.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    app.exec_()
    
    

if __name__ == '__main__':
    test_webcam_imageio()

 
