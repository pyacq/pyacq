import numpy as np

from ..core import Node, register_node_type
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import imageio
    HAVE_IMAGEIO = True
except ImportError:
    HAVE_IMAGEIO = False

import time


class ImageIOThread(QtCore.QThread):
    def __init__(self, out_stream, reader, parent=None):
        QtCore.QThread.__init__(self)
        self.out_stream= out_stream
        self.reader = reader

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        n = 0
        for im in self.reader:
            with self.lock:
                if not self.running:
                    break
            
            n += 1
            self.out_stream.send(n, im)
            # this is bad 
            # TODO : find a way to do trhis loop in blocking mode
            time.sleep(1./self.out_stream.params['sample_rate'])
    
    def stop(self):
        with self.lock:
            self.running = False


class WebCamImageIO(Node):
    """
    Simple webcam device using the imageio python module.
    """
    _output_specs = {'video': dict(streamtype='video',dtype='uint8',
                                                shape=(4800, 6400, 3), compression ='',
                                                sample_rate =1.
                                                ),
                                }
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_IMAGEIO, "WebCamAV node depends on the `imageio` package, but it could not be imported."

    

    def _configure(self, camera_num=0):
        self.camera_num = camera_num
        reader = imageio.get_reader('<video{}>'.format(self.camera_num))
        self.metadata = reader.get_meta_data()
        reader.close()
        
        s = self.metadata['size']
        self.output.spec['shape'] = (s[1], s[0], 3,)
        self.output.spec['sample_rate'] = float(self.metadata['fps'])
    
    def _initialize(self):
        pass
        
    def _start(self):
        self.reader = imageio.get_reader('<video{}>'.format(self.camera_num))
        self._thread = ImageIOThread(self.output, self.reader)
        self._thread.start()

    def _stop(self):
        self._thread.stop()
        self._thread.wait()
    
    def _close(self):
        self.reader.close()

register_node_type(WebCamImageIO)
