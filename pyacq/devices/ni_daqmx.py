import numpy as np
import collections
import logging
import ctypes

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import nidaqmx
    import nidaqmx.constants as const
    HAVE_NIDAQMX = True
except ImportError:
    HAVE_NIDAQMX = False



if HAVE_NIDAQMX:
    _ai_modes = {
        'default': const.TerminalConfiguration.DEFAULT,
        'rse': const.TerminalConfiguration.RSE,
        'nrse': const.TerminalConfiguration.NRSE,
        'diff': const.TerminalConfiguration.DIFFERENTIAL,
        'pseudodiff': const.TerminalConfiguration.PSEUDODIFFERENTIAL,
    }



class NIDAQmx(Node):
    """Simple wrapper around nidaqmx (official python wrapper of NI).
    """
    _output_specs = {
        'aichannels': {}
    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_NIDAQMX, "NIDAQmx node depends on the `nidaqmx` package, but it could not be imported."
        #~ self.poll_thread = DAQmxPollThread(self)

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

    def _configure(self, aichannels=None, aisamplerate=None,
            airanges=(-5.,5.), aimodes='nrse', chunksize=1000):
        
        self._chunksize = chunksize
        if type(airanges)!=dict and type(airanges)==tuple:
            airanges = {k:airanges for k in aichannels}
        
        if type(aimodes)!=dict and type(aimodes)==str:
            aimodes = {k:aimodes for k in aichannels}
        
        self._conf = {
            'aichannels': aichannels,
            'aisamplerate': aisamplerate,
            'airanges' : airanges,
            'aimodes' : aimodes,
            #~ 'aiclocksource': aiclocksource,
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
        sr = self._conf['aisamplerate']
        aitask = nidaqmx.Task()
        
        for chan in self._conf['aichannels']:
            terminal_config = self._conf['aimodes'].get(chan, 'nrse')
            min_val, max_val = self._conf['airanges'].get(chan, (-5., 5.))
            aitask.ai_channels.add_ai_voltage_chan(chan,
                        name_to_assign_to_channel="",
                        terminal_config=terminal_config,
                        min_val=min_val, max_val=max_val,
                        units=VoltageUnits.VOLTS,
                        custom_scale_name="")
        
        aitask.timing.cfg_samp_clk_timing(sr, source="", active_edge=const.Edge.RISING,
                        sample_mode= const.AcquisitionType.CONTINUOUS,
                        samps_per_chan=self._chunksize)
        
        in_task.register_every_n_samples_acquired_into_buffer_event(self._chunksize, self._ai_callback)
        
        self.aitask = aitask
        
    def _start(self):
        self._n = 0
        self.aitask.start()

    def _stop(self):
        self.aitask.stop()

    def _close(self):
        self.aitask.close()
    
    def _ai_callback(self, in_task_handle, every_n_samples_event_type,
                                    number_of_samples, callback_data):
        raw_data = self.aitask.in_stream.in_stream.read()
        self._n += raw_data.shape[0]
        self.outputs['aichannels'].send(self._n, raw_data)
        
        return 0



register_node_type(NIDAQmx)