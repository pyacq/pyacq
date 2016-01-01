import numpy as np
import collections
import logging

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import PyDAQmx
    from PyDAQmx.DAQmxFunctions import TaskHandle, DAQmxCreateTask, DAQmxCreateAIVoltageChan, byref
    from PyDAQmx.DAQmxConstants import DAQmx_Val_RSE, DAQmx_Val_NRSE, DAQmx_Val_DIFF
    HAVE_DAQMX = True
    _ai_modes = {'rse': DAQmx_Val_RSE, 'nrse': DAQmx_Val_NRSE, 'diff': DAQmx_Val_DIFF}
except ImportError:
    HAVE_DAQMX = False


class NIDAQmx(Node):
    """Simple wrapper around PyDAQmx for analog/digital input.
    """
    _output_spec = {
        'aichannels': {}
    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_DAQMX, "NIDAQmx node depends on the `PyDAQmx` package, but it could not be imported."

    def configure(self, *args, **kwargs):
        """
        Parameters
        ----------
        aichannels : dict
            Dict of {name: mode} for all analog input channels to record. Names
            are formatted like 'Dev1/ai0', and mode must be one of 'rse', 'nrse',
            'diff', or ...   [needs to be ordered??]
        aisamplerate : float
            Sample rate for analog input clock.
        aiclocksource : str
            Analog sample clock source (default is ...)
        chunksize : int
            Number of samples to acquire per chunk (1024 by default).
        """
        return Node.configure(self, *args, **kwargs)

    def _configure(self, aichannels=None, aisamplerate=None, aiclocksource=None,
                   chunksize=1024):
        
        self._chunksize = chunksize
        self._conf = {
            'aichannels': aichannels,
            'aisamplerate': aisamplerate,
            'aiclocksource': aiclocksource,
        }

        self.aichannels.spec.update({
            'chunksize': chunksize,
            'shape': (chunksize, len(aichannels)),
            'dtype': 'float64',
            'sample_rate': samplerate,
        })
    
    def check_input_specs(self):
        pass
    
    def check_output_specs(self):
        pass

    def _initialize(self):
        chunksize = self._chunksize
        aitask = PyDAQmx.Task()
        for chan, mode in self._conf['aichannels'].items():
            chan = chan.encode()
            aitask.CreateAIVoltageChan(chan, '', _ai_modes[mode],
                                       -10, 10, DAQmx_Val_Volts, None)
        aitask.CfgSampClkTiming("", 10000.0, DAQmx_Val_Rising, 
                                DAQmx_Val_ContSamps, chunksize)
        
        self.aitask = aitask
        
    def _start(self):
        self.aitask.StartTask()

    def _stop(self):
        self.aitask.StopTask()

    def _close(self):
        self.aitask.ClearTask()
        
    def read(self):
        read = int32()
        data = np.zeros((1000,), dtype=numpy.float64)
        self.aitask.ReadAnalogF64(1000, 10.0, DAQmx_Val_GroupByChannel, data,
                                  1000, byref(read), None)            


register_node_type(NIDAQmx)
