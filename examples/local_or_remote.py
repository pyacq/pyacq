"""
This demonstrate that any Node/NodeWidget can dealed in local QApp
the same way when the are remoted.

"""

from pyacq import create_manager, ImageViewer, WebCamAV
from pyqtgraph.Qt import QtCore, QtGui
import time
import pyqtgraph as pg





def dev_remote_viewer_local():
    man = create_manager()

    # this create the dev in a separate process (NodeGroup)
    nodegroup = man.create_nodegroup()
    
    dev = nodegroup.create_node('WebCamAV', name = 'cam0')
    dev.configure(camera_num = 0)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()

    #view is a Node in local QApp
    app = pg.mkQApp()

    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()

    dev.start()
    viewer.start()

    app.exec_()


def dev_local_viewer_local():
    # no manager
    # device + view is a Node in local QApp
    # Nodes are controled directly
    
    app = pg.mkQApp()
    
    dev = WebCamAV()
    dev.configure(camera_num = 0)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()


    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()

    dev.start()
    viewer.start()

    app.exec_()
 
 
def dev_remote_viewer_remote():
    # no QApp all Nodes are remoted even the viewer.
    # note that dev and viewer are in the same NodeGroup
    # so they are in the same process
    
    man = create_manager()
    nodegroup = man.create_nodegroup()
    
    dev = nodegroup.create_node('WebCamAV', name = 'cam0')
    dev.configure(camera_num = 0)
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    dev.initialize()
    
    viewer = nodegroup.create_node('ImageViewer', name = 'viewer0')
    viewer.configure()
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()

    dev.start()
    viewer.start()
    
    
    time.sleep(10.)


# uncomment one if this 3 lines and compare the process number
dev_remote_viewer_local()
#dev_local_viewer_local()
#dev_remote_viewer_remote()