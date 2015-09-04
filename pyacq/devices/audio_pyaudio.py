import numpy as np
import collections
import logging

from ..core import Node, register_node_type, ThreadPollInput
from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

try:
    import pyaudio
    HAVE_PYAUDIO = True
except ImportError:
    HAVE_PYAUDIO = False

if HAVE_PYAUDIO:
    format_conv = { 'int16' : pyaudio.paInt16, 'int32' : pyaudio.paInt32, 'float32' : pyaudio.paFloat32, }
    # TODO add support for 'int24' (possible in pyaudio but not in numpy)

class PyAudio(Node):
    """
    Simple wrapper with pyaudio to acess audio in/out in a Nodes.
    
    
    Parameters for configure():
    ----
    nb_channel : int
        Number of audio channel
    sampling_rate: float
        Sampling rate, not that internally sampling rate is an int so it is rounded.
    input_device_index : int or None
        Input device index (like in pyaudio)
        If None, no grabbing to audio device input so the Node have no output.
    output_device_index: in or None
        Output device index (like in pyaudio)
        If None, no playing to audio device output so the Node have no input.
    format : str in ('int16', 'int32' or 'float32')
        internal format for pyaudio.
    chunksize : int (1024 by default)
        Size of each chun. This impact latency. Too small lead to cracks.    
    """

    _input_specs = {'signals' : dict(streamtype = 'analogsignal',dtype = 'int16',
                                                shape = (-1, 2), compression ='', time_axis=0,
                                                sampling_rate =44100.
                                                )}

    _output_specs = {'signals' : dict(streamtype = 'analogsignal',dtype = 'int16',
                                                shape = (-1, 2), compression ='', time_axis=0,
                                                sampling_rate =44100.
                                                )}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYAUDIO, "PyAudio node depends on the `pyaudio` package, but it could not be imported."

    def _configure(self, nb_channel = 2, sampling_rate =44100.,
                    input_device_index = None, output_device_index = None,
                    format = 'int16', chunksize = 1024):
        
        
        self.nb_channel = nb_channel
        self.sampling_rate = sampling_rate
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
        self.format = format
        self.chunksize = chunksize
        
        assert self.format in format_conv
        
        self.pa = pyaudio.PyAudio()
        
        # check if supported
        if self.input_device_index is not None:
            assert self.pa.is_format_supported(input_format=format_conv[format], input_channels=self.nb_channel, 
                    rate=int(self.sampling_rate), input_device=self.input_device_index),\
                    'Input not supported {} {} device {}'.format(self.nchannel, samplerate, self.input_device_index)
        
        if self.output_device_index is not None:
            assert self.pa.is_format_supported(output_format=format_conv[format], output_channels=self.nb_channel, 
                    rate=int(self.sampling_rate), output_device=self.output_device_index),\
                    'Output not supported {} {} device {}'.format(self.nchannel, samplerate, self.input_device_index)

        self.output.spec['shape'] = (self.chunksize, self.nb_channel)
        self.output.spec['dtype = '] = format
        self.output.spec['sampling_rate'] = float(int(self.sampling_rate))
        gains = { 'int16' : 1./2**15, 'int32' : 1./2**31, 'float32':1. }
        self.output.spec['gain'] = gains[self.format]
        self.output.spec['offset'] = 0.
    
    def check_input_specs(self):
        pass
    
    def check_output_specs(self):
        pass

    def _initialize(self):
        self.audiostream = self.pa.open(
                    rate = int(self.sampling_rate),
                    channels = int(self.nb_channel),
                    format = format_conv[self.format],
                    input= self.input_device_index is not None,
                    output= self.output_device_index is not None,
                    input_device_index = self.input_device_index,
                    output_device_index = self.output_device_index,
                    frames_per_buffer = self.chunksize,
                    stream_callback = self._audiocallback,
                    start = False)
        self.head = 0
        
        # outbuffer
        size = self.nb_channel * self.chunksize * np.dtype(self.format).itemsize
        self.enmpty_outputbuffer = b'\x00' *  size
        self.out_queue = collections.deque()
        self.lock = Mutex()
        
        if self.output_device_index is not None:
            self.thread = ThreadPollInput(self.input, parent = self)
            self.thread.new_data.connect(self._new_output_buffer)
    
    def _start(self):
        self.audiostream.start_stream()
        if self.output_device_index is not None:
            self.thread.start()

    def _stop(self):
        self.audiostream.stop_stream()
        if self.output_device_index is not None:
            self.thread.stop()
            self.thread.wait()

    def _close(self):
        self.audiostream.close()
        self.pa.terminate()
        del self.thread

    def _audiocallback(self, in_data, frame_count, time_info, status):
        #~ print('audiocallback', len(self.out_queue))
        if in_data is not None:
            self.head += self.chunksize
            self.output.send(self.head, in_data)
        with self.lock:
            if len(self.out_queue)>0:
                out = self.out_queue.popleft()
            else:
                logging.info('Node PyAudio', self.name, 'lost output buffer')
                #~ print('lost output buffer')
                out = self.enmpty_outputbuffer
        return (out, pyaudio.paContinue)    
    
    def _new_output_buffer(self, pos, data):
        #~ print('_new_output_buffer', pos, data.shape, data.dtype)
        with self.lock:
            self.out_queue.append(bytes(data))
            
    
register_node_type(PyAudio)
