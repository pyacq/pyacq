from pyacq import create_manager, ImageViewer
import pyacq.devices.micromanager
from pyqtgraph.Qt import QtCore, QtGui

import logging
logging.getLogger().level = logging.INFO
#man = create_manager()

# this create the dev in a separate process (NodeGroup)
#nodegroup = man.create_nodegroup()
#dev = nodegroup.create_node('MicroManager', name = 'cam0')
dev = pyacq.devices.MicroManager()
dev.configure(adapter='DemoCamera', device='DCam', Exposure='100')
dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
dev.initialize()

#view is a Node in local QApp
app = QtGui.QApplication([])

viewer = ImageViewer()
viewer.configure()
viewer.input.connect(dev.output)
viewer.initialize()
viewer.show()

dev.start()
viewer.start()

app.exec_()

viewer.close()
dev.close()