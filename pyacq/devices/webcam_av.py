"""
av is python binding to libav or ffmpeg and this is so great (except the poor doc)
http://mikeboers.github.io/PyAV/index.html
"""


import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui

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
        
    def run(self):
        self.running = True
        n = 0
        stream = self.container.streams[0]
        while (self.running):
            for packet in self.container.demux(stream):
                for frame in packet.decode():
                    #~ print(frame.time, time.time(), frame.index)
                    #~ print(len(frame.planes), len(frame.planes[0].to_bytes()))
                    arr = frame.to_rgb().to_nd_array()
                    n += 1
                    self.out_stream.send(n, arr)


class WebCamAV(Node):
    _output_specs = {'video' : dict(streamtype = 'video',dtype = 'uint8',
                                                shape = (480, 640, 3), compression ='',
                                                sampling_rate =30.
                                                ),
                                }
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_AV, "WebCamAV node depends on the `av` package, but it could not be imported."
    

    def configure(self, camera_num=0, **options):
        self.camera_num = camera_num
        self.options = options
        #~ container = cv2.VideoCapture(camera_num)
        #TODO deal with metadata
        #~ del container
    
    def initialize(self):
        #~ assert self.metadata['fps'] == self.out_streams[0].params['sampling_rate']
        container = av.open('/dev/video{}'.format(self.camera_num), 'r','video4linux2', self.options)
        stream = next(s for s in container.streams if s.type == 'video')
        
        #~ stream.format.width 640
        #~ stream.format.height 480
        #~ stream.format.name 'yuyv422'
        
    def start(self):
        print('/dev/video{}'.format(self.camera_num))
        self.container = av.open('/dev/video{}'.format(self.camera_num), 'r','video4linux2')

        self._thread = AVThread(self.outputs['video'], self.container)
        self._thread.start()
        self._running = True

    def stop(self):
        self._thread.running = False
        self._thread.wait()
        self._running = False
        del(self.container)
    
    def close(self):
        self.container.close()

        
register_node_type(WebCamAV)
