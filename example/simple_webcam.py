from pyacq import create_manager, ImageViewer
from pyqtgraph.Qt import QtCore, QtGui


# create a device in a new pocess
man = create_manager()

nodegroup = man.create_nodegroup()
#dev = nodegroup.create_node('WebCamImageIO', name = 'cam0')
dev = nodegroup.create_node('WebCamAV', name = 'cam0')

dev.configure(camera_num = 0)
stream_dict = dict(protocol = 'tcp', interface = '127.0.0.1', port = '9000',
                    transfertmode = 'plaindata', streamtype = 'video',
                    dtype = 'uint8', shape = (480, 640, 3), compression ='',
                    scale = None, offset = None, units = '' , sampling_rate =30,
                    )
dev.create_outputs([ stream_dict ])    
dev.initialize()

#view in local QApp
app = QtGui.QApplication([])

viewer = ImageViewer()
viewer.configure()
viewer.set_inputs([ stream_dict ])
viewer.initialize()
viewer.show()

dev.start()
viewer.start()

app.exec_()

