from ..core import WidgetNode, register_node_type
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import pyqtgraph as pg
import vispy
import vispy.scene


class ImageViewer(WidgetNode):
    """
    A simple image viewer using pyqtgraph.
    """
    _input_specs = {'video': dict(streamtype='video',dtype='uint8',
                                                shape=(-1, -1, 3), compression ='',
                                                ),
                                }
    def __init__(self, gfxlib='pyqtgraph', **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.gfxlib = gfxlib
        if gfxlib == 'pyqtgraph':
            self.graphicsview = pg.GraphicsView()
            self.layout.addWidget(self.graphicsview)
            
            self.plot = pg.PlotItem()
            self.graphicsview.setCentralItem(self.plot)
            self.plot.getViewBox().setAspectLocked(lock=True, ratio=1)
            self.plot.hideButtons()
            self.plot.showAxis('left', False)
            self.plot.showAxis('bottom', False)
            
            self.image = pg.ImageItem()
            self.plot.addItem(self.image)
        elif gfxlib == 'vispy':
            self.canvas = vispy.scene.SceneCanvas(keys='interactive', show=True)
            self.layout.addWidget(self.canvas.native)
            self.view = self.canvas.central_widget.add_view()
            self.view.camera = vispy.scene.PanZoomCamera(aspect=1)
            self.image = vispy.scene.visuals.Image(parent=self.view.scene)
        else:
            raise ValueError('gfxlib must be "pyqtgraph" or "vispy"')
    
    def _configure(self, **kargs):
        pass
    
    def _initialize(self):
        in_params = self.input.params
        self.timer = QtCore.QTimer(singleShot=False)
        self.timer.setInterval(int(1./in_params['sample_rate']*1000))
        self.timer.timeout.connect(self.poll_socket)

    def _start(self):
        self.timer.start()

    def _stop(self):
        self.timer.stop()
    
    def _close(self):
        pass
    
    def poll_socket(self):
        event = self.input.socket.poll(0)
        if event != 0:
            index, data = self.input.recv()
            data = data[-1]  # pick most recent frame
            if self.gfxlib == 'pyqtgraph':
                data = data[::-1]  # invert y axis
                data = data.swapaxes(0,1)
                self.image.setImage(data)
            else:
                self.image.set_data(data)
                self.view.camera.set_range()


register_node_type(ImageViewer)

