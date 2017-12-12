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
    
    The main scenario is : continuous acquisition on AI channels giving an
    pyacq output stream. While playing some short waveform on one or 
    several AO channels asynchronously.
    
    

    Parameters for configure
    ----------
    aichannels : list
        List of channel with the NI name ['Dev1/ai0', 'Dev1/ai1', ...]
    sample_rate : float
        Sample rate for analog input clock.
    airanges: dict or tuple
        A dict of tuple that represent the range (min_val, max_va) in volts.
        { 'Dev1/ai0': (-5, 5),  'Dev1/ai1':(-5,5) ...}
        If a tuple is given then it is applyed to all channels.
    aimodes : dict or str
        A dict that give the mode (Terminal Configuration) for
        each channel, must be in ('rse',  'nrse', 'diff', 'pseudodiff')
        See NI doc for that.
        { 'Dev1/ai0': rse,  'Dev1/ai1':rse ...}
        If a str is given then it is applyed to all channels.
    chunksize : int
        Number of samples to acquire per chunk per channel (1000 by default).
        Must compatible with internal fifo size of the device depending the nb
        of channel. If you have an error from nidaqmx like **To keep DMA or USB Bulk as...**
        change this value.
    magnitude_mode: str 'raw', 'float32_volt', 'float64_volt'
        Change the dtype of the output 'aichannels'
          * 'raw' represent the int directly from the board. 
          * 'float32_volt' and 'float64_volt' are the scale value in volts


    """
    _output_specs = {
        'aichannels': {}
    }

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_NIDAQMX, "NIDAQmx node depends on the `nidaqmx` package, but it could not be imported."

    def _configure(self, sample_rate=None,  chunksize=1000,
            aichannels=[], airanges=(-5.,5.), aimodes='rse', magnitude_mode='raw',
            aochannels=[]):
        
        self._chunksize = chunksize
        if type(airanges)!=dict and type(airanges)==tuple:
            airanges = {k:airanges for k in aichannels}
        
        if type(aimodes)!=dict and type(aimodes)==str:
            aimodes = {k:aimodes for k in aichannels}
        
        self._nb_ai_channel = len(aichannels)
        self._nb_ao_channel = len(aochannels)
        
        self._conf = {
            'aichannels': aichannels,
            'sample_rate': sample_rate,
            'airanges' : airanges,
            'aimodes' : aimodes,
            'aochannels' : aochannels,
        }
        
        self._ai_dt = {'raw': 'int16',  'float32_volt':'float32',  'float64_volt':'float64'}[magnitude_mode]
        self.outputs['aichannels'].spec.update({
            'chunksize': chunksize,
            'shape': (chunksize, self._nb_ai_channel),
            'dtype': self._ai_dt,
            'sample_rate': sample_rate,
            'nb_channel': len(aichannels),
        })
        
        self.magnitude_mode = magnitude_mode
        if self.magnitude_mode!='raw':
            #TODO: change this when raw is not int16
            self._ai_gains = []
            for k in aichannels:
                min_val, max_val = airanges[k]
                gain = (max_val-min_val)/2**16
                self._ai_gains.append(gain)
            self._ai_gains = np.array(self._ai_gains, dtype=self._ai_dt).reshape(1, -1)
        
        
        
    def check_input_specs(self):
        pass
    
    def check_output_specs(self):
        pass

    def _initialize(self):
        sr = self._conf['sample_rate']
        
        if self._nb_ai_channel>0:
            aitask = nidaqmx.Task()
            
            for chan in self._conf['aichannels']:
                terminal_config = _ai_modes[self._conf['aimodes'].get(chan, 'nrse')]
                min_val, max_val = self._conf['airanges'].get(chan, (-5., 5.))
                aitask.ai_channels.add_ai_voltage_chan(chan,
                            name_to_assign_to_channel="",
                            terminal_config=terminal_config,
                            min_val=min_val, max_val=max_val,
                            units=const.VoltageUnits.VOLTS,
                            custom_scale_name="")
            
            aiClockSource = ""
            
            aitask.timing.cfg_samp_clk_timing(sr, source=aiClockSource, active_edge=const.Edge.RISING,
                            sample_mode= const.AcquisitionType.CONTINUOUS,
                            samps_per_chan=self._chunksize)
            
            self.thread = DAQmxPollThread(self, parent=None)
        else:
            aitask = None
        
        self.aitask = aitask
        self.aotask = None
    
    def _start(self):
        self._n = 0
        if self.aitask is not None:
            self.aitask.start()
            self.thread.start()

    def _stop(self):
        if self.aitask is not None:
            self.thread.stop()
            self.aitask.stop()

    def _close(self):
        if self.aitask is not None:
            self.aitask.close()
    
    def play_ao(self, aochannels, sigs):
        if self.aotask is not None:
            #one play is already running
            return
        
        sr = self._conf['sample_rate']
        
        self.aotask = nidaqmx.Task()
        
        for chan in aochannels:
            min_val, max_val = -10., 10.
            self.aotask.ao_channels.add_ao_voltage_chan(chan,
                        name_to_assign_to_channel="",
                        min_val=min_val, max_val=max_val,
                        units=const.VoltageUnits.VOLTS,
                        custom_scale_name="")
        
        if self._nb_ai_channel>0:
            aoClockSource = "/Dev1/ai/SampleClock"
        else:
            aoClockSource = ""
        self.aotask.timing.cfg_samp_clk_timing(sr, source= "", active_edge=const.Edge.RISING,
                        sample_mode=const.AcquisitionType.FINITE,
                        samps_per_chan=sigs.shape[1])

        self.aotask.out_stream.output_buf_size = sigs.shape[1]
        self.aotask.register_done_event(self._on_ao_done)
        self.aotask.write(sigs, auto_start=False)
        self.aotask.start()


    def _on_ao_done(self, task_handle, status, callback_data):
        self.aotask.close()
        self.aotask = None
        return 0

class DAQmxPollThread(QtCore.QThread):
    def __init__(self, node, parent=None):
        QtCore.QThread.__init__(self, parent=parent)
        self.node = node

        self.lock = Mutex()
        self.running = False
        
    def run(self):
        with self.lock:
            self.running = True
        
        aitask = self.node.aitask
        buffer_time = self.node._chunksize / self.node._conf['sample_rate']
        aitask.in_stream.timeout = buffer_time*10.
        
        raw_data = np.zeros((self.node._chunksize, self.node._nb_ai_channel), dtype='int16')
        raw_data_flat = raw_data
        raw_data_flat.reshape(-1)
        
        stream = self.node.outputs['aichannels']
        
        n = 0
        while True:
            with self.lock:
                if not self.running:
                    break
            
            nb_sample = aitask.in_stream.readinto(raw_data_flat)
            if nb_sample==0:
                continue
            
            n += raw_data.shape[0]

            if self.node.magnitude_mode=='raw':
                stream.send(raw_data, index=n)
            else:
                scaled_data = raw_data.astype(self.node._ai_dt)
                scaled_data *= self.node._ai_gains
                stream.send(scaled_data, index=n)

    def stop(self):
        with self.lock:
            self.running = False



register_node_type(NIDAQmx)
