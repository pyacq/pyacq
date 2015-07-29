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
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'video',
                        dtype = 'uint8', shape = (480, 640, 3), compression ='',
                        scale = None, offset = None, units = '' , sampling_rate =30,
                        )
    dev.create_outputs([ stream_dict ])    
    dev.initialize()
    
    viewer = ImageViewer()
    viewer.configure()
    viewer.set_inputs([ stream_dict ])
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()
    
    timer = QtCore.QTimer(singleShot = True, interval = 5000)
    #~ timer.timeout.connect(viewer.stop)
    #~ timer.timeout.connect(dev.stop)
    timer.timeout.connect(viewer.close)
    
    #~ timer.timeout.connect(app.quit)
    #~ timer.timeout.connect(end)
    
    timer.start()
    
    app.exec_()

if __name__ == '__main__':
    test_webcam_opencv()

 
