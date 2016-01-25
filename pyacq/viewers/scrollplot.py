from ..core import WidgetNode, register_node_type
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import pyqtgraph as pg
import vispy
import vispy.scene
import OpenGL  # vispy requires this for scrolling plots to work


class ScrollPlot(WidgetNode):
    """
    A scrolling plot viewer node.
    """
    _input_specs = {'input': dict(streamtype='analogsignal')}
    
    def __init__(self, **kargs):
        WidgetNode.__init__(self, **kargs)
        
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        
        self.canvas = vispy.scene.SceneCanvas(keys='interactive', show=True)
        self.layout.addWidget(self.canvas.native)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = vispy.scene.PanZoomCamera()
        
    def _configure(self):
        pass
        
    def _initialize(self):
        in_params = self.input.params
        
        history = 5000
        rows, cols = in_params['shape'][1:]
        yscale = 100.
        self.lines = vispy.scene.ScrollingLines(n_lines=rows*cols, line_size=history,
                                          columns=cols, dx=0.8/history, cell_size=(1, 1/yscale),
                                          parent=self.view.scene)
        self.lines.transform = vispy.scene.STTransform(scale=(1, yscale))
        self.view.camera.rect = [-1, -1, rows+1, cols+1]
        
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
            data = data.astype('float32').reshape(data.shape[0], data.shape[1]*data.shape[2]).T
            self.lines.roll_data(data)

register_node_type(ScrollPlot)
