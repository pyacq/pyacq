"""
av is python binding to libav or ffmpeg and this is so great (except the poor doc for the moment)
http://mikeboers.github.io/PyAV/index.html
"""


import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import av
    HAVE_AV = True
except ImportError:
    HAVE_AV = False

import time


class AVThread(QtCore.QThread):
    def __init__(self, out_stream, container, parent=None):
        QtCore.QThread.__init__(self)
        self.out_stream = out_stream
        self.container = container

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        n = 0
        stream = self.container.streams[0]

        for packet in self.container.demux(stream):
            with self.lock:
                if not self.running:
                    break
            for frame in packet.decode():
                arr = frame.to_rgb().to_nd_array()
                n += 1
                self.out_stream.send(n, arr)

    def stop(self):
        with self.lock:
            self.running = False


class WebCamAV(Node):
    """
    Simple webcam device using the `av` python module, which is a wrapper around
    ffmpeg or libav.
    
    See http://mikeboers.github.io/PyAV/index.html.
    """
    _output_specs = {'video': dict(streamtype='video',dtype='uint8',
                                                shape=(4800, 6400, 3), compression ='',
                                                sampling_rate = 1.)
                                }
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_AV, "WebCamAV node depends on the `av` package, but it could not be imported."
    

    def _configure(self, camera_num=0, **options):
        self.camera_num = camera_num
        self.options = options

        container = av.open('/dev/video{}'.format(self.camera_num), 'r','video4linux2', self.options)
        stream = next(s for s in container.streams if s.type == 'video')
        self.output.spec['shape'] = (stream.format.height, stream.format.width, 3)
        self.output.spec['sampling_rate'] = float(stream.average_rate)
    
    def _initialize(self):
        pass
    
    def _start(self):
        self.container = av.open('/dev/video{}'.format(self.camera_num), 'r','video4linux2', self.options)

        self._thread = AVThread(self.output, self.container)
        self._thread.start()

    def _stop(self):
        self._thread.stop()
        self._thread.wait()
        self._running = False
        del(self.container)
    
    def _close(self):
        pass

register_node_type(WebCamAV)
