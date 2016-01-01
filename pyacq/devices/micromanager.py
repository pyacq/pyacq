import sys
import numpy as np
import collections
import logging

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import MMCorePy
    HAVE_MM = True
except ImportError:
    try:
        # MM does not install itself to standard path..
        sys.path.append('C:\\Program Files\\Micro-Manager-1.4')
        import MMCorePy
        sys.path.pop()
        HAVE_MM = True
    except ImportError:
        HAVE_MM = False


class MicroManager(Node):
    """Support for cameras accessed via MicroManager.
    """
    _output_spec = {
        'video': {}
    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_MM, "MicroManager node depends on the `MMCorePy` package, but it could not be imported."

    def configure(self, *args, **kwargs):
        """
        Parameters
        ----------
        adapter : str
            Name of MicroManager adapter to use.
        device : str
            Name of camera device to open.
        binning: str
            Binning value to use (default is '1x1')
        exposure : float
            Exposure time in seconds
        trigger : str
            Trigger mode ('NORMAL' or 'START')
        region : tuple or None
            Region of interest to acquire from as (x, y, w, h). If None, then
            record from the entire sensor.
        """
        return Node.configure(self, *args, **kwargs)

    def _configure(self, adapter='', device='', binning='1x1', exposure=10e-3, trigger='NORMAL', region=None):
        self.mmc = MMCorePy.CMMCore()

        # sanity check for MM adapter and device name
        all_adapters = self.mmc.getDeviceAdapterNames()
        if adapter not in all_adapters:
            raise ValueError("Adapter name '%s' is not valid. Options are: %s" % (adapter, all_adapters))
        all_devices = self.mmc.getAvailableDevices(adapter)
        if device not in all_devices:
            raise ValueError("Device name '%s' is not valid for adapter '%s'. Options are: %s" % (device, adapter, all_devices))

        self.cam_name = adapter + '_' + device
        self.mmc.loadDevice(self.cam_name, adapter, device)
        self.mmc.initializeDevice(self.cam_name)
        self._conf = binning, exposure, trigger, region
    
    def check_input_specs(self):
        pass
    
    def check_output_specs(self):
        pass

    def _initialize(self):
        binning, exposure, trigger, region = self._conf
        self.mmc.setCameraDevice(self.cam_name)
        self.mmc.setProperty(self.cam_name, 'Binning', binning)
        if region is None:
            self.mmc.clearROI()
        else:
            self.mmc.setROI(*region)
        self.mmc.setProperty(self.cam_name, 'Exposure', str(exposure))
        self.mmc.setProperty(self.cam_name, 'Trigger', trigger)
        
    def _start(self):
        self.mmc.startContinuousSequenceAcquisition(0)
        
    def _stop(self):
        self.mmc.stopSequenceAcquisition()

    def _close(self):
        self.mmc.unloadDevice(self.cam_name)
        
    def read(self):
        frames = []
        for i in self.mmc.getRemainingImageCount():
            frames.append(self.mmc.popNextImage())
        return frames
        


register_node_type(MicroManager)
