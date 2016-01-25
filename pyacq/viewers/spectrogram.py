from ..core import WidgetNode, register_node_type
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np
import pyqtgraph as pg
import vispy
import vispy.scene


class Spectrogram(WidgetNode):
    """
    A spectrogram viewer node.
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
        
        fft_samples = 512
        self.window = np.hanning(fft_samples)
        self.buffer = np.zeros(fft_samples, dtype='float32')
        
        history = 1000
        self.image = ScrollingImage((1 + fft_samples // 2, history), parent=self.view.scene)
        #self.image.transform = vispy.scene.LogTransform((0, 10, 0))
        #self.view.camera.rect = (-29.3409, 2.53991, 567.269, 1.10259)
    
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
            self.buffer = np.roll(self.buffer, -data.shape[0])
            self.buffer[-data.shape[0]:] = data
            fft = np.abs(np.fft.rfft(self.buffer * self.window)).astype('float32')
            self.image.roll(fft)
            self.view.camera.set_range()

register_node_type(Spectrogram)




# Copied from vispy/examples/demo/scene/oscilloscope.py

rolling_tex = """
float rolling_texture(vec2 pos) {
    if( pos.x < 0 || pos.x > 1 || pos.y < 0 || pos.y > 1 ) {
        return 0.0f;
    }
    vec2 uv = vec2(mod(pos.x+$shift, 1), pos.y);
    return texture2D($texture, uv).r;
}
"""

cmap = """
vec4 colormap(float x) {
    return vec4(x/5e2, x/2e1, x/1e0, 1); 
}
"""

from vispy import scene, visuals, gloo

class ScrollingImage(scene.Image):
    def __init__(self, shape, parent):
        self._shape = shape
        self._color_fn = visuals.shaders.Function(rolling_tex)
        self._ctex = gloo.Texture2D(np.zeros(shape+(1,), dtype='float32'),
                                    format='luminance', internalformat='r32f')
        self._color_fn['texture'] = self._ctex
        self._color_fn['shift'] = 0
        self.ptr = 0
        scene.Image.__init__(self, method='subdivide', grid=(10, 10), parent=parent)
        #self.set_gl_state('additive', cull_face=False)
        self.shared_program.frag['get_data'] = self._color_fn
        cfun = visuals.shaders.Function(cmap)
        self.shared_program.frag['color_transform'] = cfun
        
    @property
    def size(self):
        return self._shape

    def roll(self, data):
        data = data.reshape(data.shape[0], 1, 1)
        
        self._ctex[:, self.ptr] = data
        self._color_fn['shift'] = (self.ptr+1) / self._shape[1]
        self.ptr = (self.ptr + 1) % self._shape[1]
        self.update()

    def _prepare_draw(self, view):
        if self._need_vertex_update:
            self._build_vertex_data()
            
        if view._need_method_update:
            self._update_method(view)
