"""
Simple webcam viewer

Streams video frames from a WebCamAV Node to an ImageViewer Node.
"""
from pyacq import create_manager, ImageViewer
from pyqtgraph.Qt import QtCore, QtGui


man = create_manager()

# this create the dev in a separate process (NodeGroup)
nodegroup = man.create_nodegroup()
dev = nodegroup.create_node('WebCamAV', name = 'cam0')
dev.configure(camera_num = 0)
dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfermode = 'plaindata')
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

