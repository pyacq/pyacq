import time

from pyacq import create_manager
from pyacq.devices.webcam_av import WebCamAV
from pyacq.viewers.imageviewer import ImageViewer

from pyqtgraph.Qt import QtCore, QtGui

#~ import logging
#~ logging.getLogger().level=logging.INFO

def test_webcam_opencv():
    # in main App
    app = QtGui.QApplication([])
    
    dev = WebCamAV(name = 'cam')
    dev.configure(camera_num = 0)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.initialize()
    
    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 5000)
    timer.timeout.connect(viewer.close)
    timer.start()
    app.exec_()

if __name__ == '__main__':
    test_webcam_opencv()

 
