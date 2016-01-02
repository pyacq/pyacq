import sys
import numpy as np
import collections
import logging

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex



class MicroManager(Node):
    """Support for cameras accessed via MicroManager.
    """
    _output_specs = {
        'video': {'streamtype': 'video'}
    }

    def __init__(self, **kargs):
        # Import here so we can make the class available without attempting
        # the MMCorePy import
        try:
            import MMCorePy
        except ImportError:
            # MM does not install itself to standard path. User needs to make sure
            # it is importable, but we can try a few standard locations:
            if sys.platform == 'win32':
                sys.path.append('C:\\Program Files\\Micro-Manager-1.4')
            elif sys.platform == 'linux':
                sys.path.append('/usr/local/ImageJ')
            else:
                raise
            import MMCorePy
            sys.path.pop()
        
        self.mmc = MMCorePy.CMMCore()
        
        Node.__init__(self, **kargs)
        self.poller = MMPollThread(self)

    def configure(self, *args, **kwargs):
        """
        Parameters
        ----------
        adapter : str
            Name of MicroManager adapter to use.
        device : str
            Name of camera device to open.
        properties : dict
            Dictionary of camera properties to set. These depend on the capabilities
            of the camera. Common properties are 'Exposure', 'Binning', and 'Trigger'.
            All values must be strings. One special property 'Region' accepts a
            (x, y, w, h) tuple of ints.
        """
        return Node.configure(self, *args, **kwargs)

    def _configure(self, adapter='', device='', **kwds):

        # Sanity check for MM adapter and device name
        all_adapters = self.mmc.getDeviceAdapterNames()
        if adapter not in all_adapters:
            raise ValueError("Adapter name '%s' is not valid. Options are: %s" % (adapter, all_adapters))
        all_devices = self.mmc.getAvailableDevices(adapter)
        if device not in all_devices:
            raise ValueError("Device name '%s' is not valid for adapter '%s'. Options are: %s" % (device, adapter, all_devices))

        # Configure camera
        self.cam_name = adapter + '_' + device
        self.mmc.loadDevice(self.cam_name, adapter, device)
        self.mmc.initializeDevice(self.cam_name)
        self._conf = kwds
        
        # Configure stream for pixel type and image size
        px_type = self.mmc.getProperty(self.cam_name, 'PixelType')
        dtype = {
            '16bit': np.uint16,
            '8bit': np.uint8,
        }[px_type]
        
        roi = self.mmc.getROI(self.cam_name)
        binn = [int(x) for x in self.mmc.getProperty(self.cam_name, 'Binning').split('x')]
        if len(binn) == 1:
            binn = binn * 2
        w = roi[2] // binn[0]
        h = roi[3] // binn[1]
        
        self.outputs['video'].spec.update({
            'shape': (h, w),
            'dtype': dtype,
        })
        
    
    def check_input_specs(self):
        pass
    
    def check_output_specs(self):
        pass

    def _initialize(self):
        self.mmc.setCameraDevice(self.cam_name)
        for prop, value in self._conf.items():
            if prop == 'Region':
                self.mmc.setROI(*value)
            else:
                self.mmc.setProperty(self.cam_name, prop, value)
        
    def _start(self):
        self.mmc.startContinuousSequenceAcquisition(0)
        self.poller.start()
        
    def _stop(self):
        self.poller.stop()
        self.mmc.stopSequenceAcquisition()

    def _close(self):
        self.stop()
        self.mmc.unloadDevice(self.cam_name)
        
    def _read_frames(self):
        frames = []
        for i in range(self.mmc.getRemainingImageCount()):
            frames.append(self.mmc.popNextImage())
        return frames
        

class MMPollThread(QtCore.QThread):
    def __init__(self, node):
        QtCore.QThread.__init__(self)
        self.node = node

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        n = 0
        node = self.node
        stream = node.outputs['video']
        
        while True:
            with self.lock:
                if not self.running:
                    break
            frames = node._read_frames()
            if len(frames) == 0:
                time.sleep(0.05)
            #print("send %d frames" % len(frames))
            for frame in frames:
                n += 1
                stream.send(n, frame)

    def stop(self):
        with self.lock:
            self.running = False



register_node_type(MicroManager)
