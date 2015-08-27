from ..core import WidgetNode
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import vispy
import vispy.scene

class ImageViewer(WidgetNode):
    """
    This simple Viewer is here for debug purpose my knowledge in vispy are too small...
    
    """
    _input_specs = {'video' : dict(streamtype = 'video',dtype = 'uint8',
                                                shape = (-1, -1, 3), compression ='',
                                                ),
                                }
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.canvas = vispy.scene.SceneCanvas(keys='interactive', show=True)
        self.layout.addWidget(self.canvas.native)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = vispy.scene.PanZoomCamera(aspect=1)
        #~ self.view.camera = vispy.scene.MagnifyCamera(aspect=1)
        
        
    def start(self):
        self.timer.start()
        self._running = True

    def stop(self):
        self.timer.stop()
        self._running = False
    
    def close(self):
        pass
    
    def initialize(self):
        in_params = self.input.params
        img_data = np.zeros(in_params['shape']).astype(in_params['dtype'])
        self.image = vispy.scene.visuals.Image(img_data, parent=self.view.scene)
        # please luke hepl me here I do not known how to range the image in the full canvas
        self.view.camera.rect = (0,0) + tuple(in_params['shape'][:2])
        
        self.timer = QtCore.QTimer(singleShot=False)
        self.timer.setInterval(int(1./in_params['sampling_rate']*1000))
        self.timer.timeout.connect(self.poll_socket)

    def configure(self, **kargs):
        pass
    
    def poll_socket(self):
        event =  self.input.socket.poll(0)
        if event != 0:
            index, data = self.input.recv()
            # this is a vertical flip
            # this should be done in GPU 
            # please help
            data = data[::-1,:,:]
            self.image.set_data(data)
            self.image.update()