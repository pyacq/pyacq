from pyacq import create_manager, ImageViewer
from pyqtgraph.Qt import QtCore, QtGui


# create a device in a new pocess
#~ man = create_manager()
#~ nodegroup = man.create_nodegroup()
#~ dev = nodegroup.create_node('WebCamImageIO', name = 'cam0')

# create a device in the main loop
from pyacq import WebCamImageIO
dev = WebCamImageIO(name = 'cam0')

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


#for the moment the process continue to live so there is no end
#we shcould avoid this
man.default_host().close()
man.close()