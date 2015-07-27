from ..core import WidgetNode
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import vispy
import vispy.scene

class ImageViewer(WidgetNode):
    """
    This simple Viewer is here for debug purpose my knowledge in vispy are too small...
    
    """
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.canvas = vispy.scene.SceneCanvas(keys='interactive', show=True)
        self.layout.addWidget(self.canvas.native)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = vispy.scene.PanZoomCamera(aspect=1)
        
    def start(self):
        self.timer.start()
        self._running = True

    def stop(self):
        self.timer.stop()
        self._running = False
    
    def close(self):
        pass
    
    def initialize(self):
        assert len(self.in_streams)!=0, 'create_outputs must be call first'
        self.stream =self.in_streams[0]
        
        shape = self.stream.params['shape']
        img_data = np.zeros(shape).astype(self.stream.params['dtype'])
        self.image = vispy.scene.visuals.Image(img_data, parent=self.view.scene)
        # please luke hepl me here I do not known how to range the image in the full canvas
        self.view.camera.rect = (0,0) + tuple(shape[:2])
        
        self.timer = QtCore.QTimer(singleShot = False)
        self.timer.setInterval(int(1./self.stream.params['sampling_rate']*1000))
        self.timer.timeout.connect(self.poll_socket)

    def configure(self, **kargs):
        pass
    
    def poll_socket(self):
        event = self.stream.socket.poll(0)
        if event!=0:
            index, data = self.stream.recv()
            # this is a vertical flip
            # this should be done in GPU 
            # please help
            data = data[::-1,:,:]
            self.image.set_data(data)
            self.image.update()
