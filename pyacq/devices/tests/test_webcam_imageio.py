import time

from pyacq import create_manager
from pyacq.devices.webcam_imageio import WebCamImageIO

from pyqtgraph.Qt import QtCore, QtGui

#~ import logging
#~ logging.getLogger().level=logging.INFO

def test_webcam_imageio():
    # in main App
    app = QtGui.QApplication([])
    
    dev = WebCamImageIO(name = 'cam0')
    dev.configure(camera_num = 0)
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'video',
                        dtype = 'uint8', shape = (480, 640, 3), compression ='',
                        scale = None, offset = None, units = '' , sampling_rate =30,
                        )
    dev.create_outputs([ stream_dict ])    
    dev.initialize()
    dev.start()
    
    timer = QtCore.QTimer(singleShot = True, interval = 5000)
    timer.timeout.connect(dev.stop)
    timer.timeout.connect(app.quit)
    timer.start()
    
    app.exec_()

def test_webcam_imageio2():
    # in node group
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    dev = nodegroup.create_node('WebCamImageIO', name = 'cam0')
    dev.configure(camera_num = 0)
    stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                        transfertmode = 'plaindata', streamtype = 'video',
                        dtype = 'uint8', shape = (480, 640, 3), compression ='',
                        scale = None, offset = None, units = '' , sampling_rate =30,
                        )
    dev.create_outputs([ stream_dict ])    
    dev.initialize()
    
    # create stream
    #~ nodegroup.register_node_from_module('pyacq.core.tests.fakenodes', 'FakeReceiver' )
    #~ receivers = [ nodegroup.create_node('FakeReceiver', name = 'receiver{}'.format(i)) for i in range(3) ]
    #~ for receiver in receivers:
        #~ receiver.configure()
        #~ receiver.set_inputs([ stream_dict ])
        #~ receiver.initialize()
    
    nodegroup.start_all_nodes()
    
    print(nodegroup.any_node_running())
    time.sleep(5.)
    
    nodegroup.stop_all_nodes()
    print(nodegroup.any_node_running())

    man.default_host().close()
    man.close()


if __name__ == '__main__':
    test_webcam_imageio()
    #~ test_webcam_imageio2()

 
