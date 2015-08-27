import time

from pyacq import create_manager
from pyacq.devices.webcam_av import WebCamAV, HAVE_AV
from pyacq.viewers.imageviewer import ImageViewer

from pyqtgraph.Qt import QtCore, QtGui

import pytest

@pytest.mark.skipif(not HAVE_AV)
def test_webcam_opencv():
    # in main App
    app = QtGui.QApplication([])
    
    dev = WebCamAV(name = 'cam')
    dev.configure(camera_num = 0)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.initialize()
    print(dev.output.params)
    
    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 3000)
    timer.timeout.connect(viewer.close)
    timer.start()
    app.exec_()

if __name__ == '__main__':
    test_webcam_opencv()
