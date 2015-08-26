import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui

try:
    import imageio
    HAVE_IMAGEIO = True
except ImportError:
    HAVE_IMAGEIO = False

import time

class ImageIOThread(QtCore.QThread):
    def __init__(self, out_stream, reader, parent = None):
        QtCore.QThread.__init__(self)
        self.out_stream= out_stream
        self.reader = reader
        
    def run(self):
        self.running = True
        n = 0
        while (self.running):
            for im in self.reader:
                n += 1
                self.out_stream.send(n, im)
                # this is bad 
                # TODO : find a way to do trhis loop in blocking mode
                time.sleep(1./self.out_stream.params['sampling_rate'])


class WebCamImageIO(Node):
    _output_specs = {'video' : dict(streamtype = 'video',dtype = 'uint8',
                                                shape = (480, 640, 3), compression ='',
                                                sampling_rate =30.
                                                ),
                                }
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_IMAGEIO, "WebCamAV node depends on the `imageio` package, but it could not be imported."

    

    def configure(self, camera_num = 0):
        self.camera_num = camera_num
        reader = imageio.get_reader('<video{}>'.format(self.camera_num))
        self.metadata = reader.get_meta_data()
        print(self.metadata)
        reader.close()
    
    def initialize(self):
        print(self.metadata['fps'])
        #~ assert self.metadata['fps'] == self.out_streams[0].params['sampling_rate']
        
    def start(self):
        self.reader = imageio.get_reader('<video{}>'.format(self.camera_num))
        self._thread = ImageIOThread(self.output, self.reader)
        self._thread.start()
        self._running = True
        print('started')

    def stop(self):
        print('stop')
        self._thread.running = False
        self._thread.wait()
        
        self._running = False
    
    def close(self):
        self.reader.close()
        

register_node_type(WebCamImageIO)

