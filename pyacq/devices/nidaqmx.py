import numpy as np
import collections
import logging
import ctypes

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import PyDAQmx
    from PyDAQmx.DAQmxFunctions import TaskHandle, DAQmxCreateTask, DAQmxCreateAIVoltageChan, byref, int32
    from PyDAQmx import DAQmxConstants as const
    HAVE_DAQMX = True
    _ai_modes = {
        'rse': const.DAQmx_Val_RSE, 
        'nrse': const.DAQmx_Val_NRSE, 
        'diff': const.DAQmx_Val_Diff,
        'pseudodiff': const.DAQmx_Val_PseudoDiff
    }
except ImportError:
    HAVE_DAQMX = False


class NIDAQmx(Node):
    """Simple wrapper around PyDAQmx for analog/digital input.
    """
    _output_specs = {
        'aichannels': {}
    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_DAQMX, "NIDAQmx node depends on the `PyDAQmx` package, but it could not be imported."
        self.poll_thread = DAQmxPollThread(self)

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

        self.outputs['aichannels'].spec.update({
            'chunksize': chunksize,
            'shape': (chunksize, len(aichannels)),
            'dtype': 'float64',
            'sample_rate': aisamplerate,
            'nb_channel': len(aichannels),
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
            aitask.CreateAIVoltageChan(chan, '', _ai_modes[mode.lower()],
                                       -10, 10, const.DAQmx_Val_Volts, None)
        aitask.CfgSampClkTiming("", 10000.0, const.DAQmx_Val_Rising, 
                                const.DAQmx_Val_ContSamps, chunksize)
        
        self.aitask = aitask
        
    def _start(self):
        self.aitask.StartTask()
        self.poll_thread.start()

    def _stop(self):
        self.poll_thread.stop()
        self.aitask.StopTask()

    def _close(self):
        self.aitask.ClearTask()
        
    def read(self):
        read = int32()
        nchan = len(self._conf['aichannels'])
        data = np.empty((self._chunksize, nchan), dtype=np.float64)
        self.aitask.ReadAnalogF64(self._chunksize, 10.0, const.DAQmx_Val_GroupByChannel, data,
                                  data.size, byref(read), None)

        # what to do if read is < chunksize?
        return data


class DAQmxPollThread(QtCore.QThread):
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
        stream = node.outputs['aichannels']
        
        while True:
            with self.lock:
                if not self.running:
                    break
                
            # are NI functions thread safe?
            data = node.read()
            
            if data.shape[0] == 0:
                time.sleep(0.05)
            n += data.shape[0]
            stream.send(n, data)

    def stop(self):
        with self.lock:
            self.running = False


register_node_type(NIDAQmx)
