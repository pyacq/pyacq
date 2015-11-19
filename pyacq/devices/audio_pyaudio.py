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
    format_conv = {'int16': pyaudio.paInt16, 'int32': pyaudio.paInt32, 'float32': pyaudio.paFloat32, }
    # TODO add support for 'int24' (possible in pyaudio but not in numpy)


class PyAudio(Node):
    """Simple wrapper around PyAudio for input and output to audio devices.
    """

    _input_specs = {'signals': dict(streamtype='analogsignal',dtype='int16',
                                                shape=(-1, 2), compression ='', time_axis=0,
                                                sample_rate =44100.
                                                )}

    _output_specs = {'signals': dict(streamtype='analogsignal',dtype='int16',
                                                shape=(-1, 2), compression ='', time_axis=0,
                                                sample_rate =44100.
                                                )}

    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        assert HAVE_PYAUDIO, "PyAudio node depends on the `pyaudio` package, but it could not be imported."
        self.pa = pyaudio.PyAudio()

    def configure(self, *args, **kwargs):
        """
        Parameters
        ----------
        nb_channel : int
            Number of audio channels
        sample_rate: float
            Sample rate. This value is rounded to integer.
        input_device_index : int or None
            Input device index (see `list_device_specs()` and pyaudio documentation).
            If None then no recording will be requested from the device, and the
            node will have no output.
        output_device_index: in or None
            Output device index (see `list_device_specs()` and pyaudio documentation).
            If None then no playback will be requested from the device, and the
            node will have no input.
        format : str in ('int16', 'int32' or 'float32')
            Internal data format for pyaudio.
        chunksize : int (1024 by default)
            Size of each chunk. Smaller chunks result in lower overall latency,
            but may also cause buffering issues (cracks/pops in sound).
        """
        return Node.configure(self, *args, **kwargs)

    def _configure(self, nb_channel=2, sample_rate=44100.,
                    input_device_index=None, output_device_index=None,
                    format='int16', chunksize=1024):
        
        
        self.nb_channel = nb_channel
        self.sample_rate = sample_rate
        self.input_device_index = input_device_index
        self.output_device_index = output_device_index
        self.format = format
        self._chunksize = chunksize
        
        assert self.format in format_conv
        
        
        # check if supported
        if self.output_device_index is not None:
            try:
                self.pa.is_format_supported(self.sample_rate, output_format=format_conv[format],
                    output_channels=self.nb_channel, output_device=self.output_device_index)
            except ValueError as err:
                msg = 'Output not supported: channels={} samplerate={} device_id={}'.format(self.nb_channel, self.sample_rate, self.output_device_index)
                raise ValueError(msg) from err
        
        if self.input_device_index is not None:
            try:
                self.pa.is_format_supported(self.sample_rate, input_format=format_conv[format],
                    input_channels=self.nb_channel, input_device=self.input_device_index)
            except ValueError as err:
                msg = 'Input not supported: channels={} samplerate={} device_id={}'.format(self.nb_channel, self.sample_rate, self.input_device_index)
                raise ValueError(msg) from err

        self.output.spec['shape'] = (chunksize, self.nb_channel)
        self.output.spec['dtype = '] = format
        self.output.spec['sample_rate'] = float(int(self.sample_rate))
        gains = {'int16': 1./2**15, 'int32': 1./2**31, 'float32':1.}
        self.output.spec['gain'] = gains[self.format]
        self.output.spec['offset'] = 0.
    
    def check_input_specs(self):
        pass
    
    def check_output_specs(self):
        pass

    def list_device_specs(self):
        return [self.pa.get_device_info_by_index(i) for i in range(self.pa.get_device_count())]

    def default_input_device(self):
        """Return the index of the default input device.
        """
        return self.pa.get_default_input_device_info()['index']
    
    def default_output_device(self):
        """Return the index of the default output device.
        """
        return self.pa.get_default_output_device_info()['index']

    def _initialize(self):
        self.audiostream = self.pa.open(
                    rate=int(self.sample_rate),
                    channels=int(self.nb_channel),
                    format=format_conv[self.format],
                    input=self.input_device_index is not None,
                    output=self.output_device_index is not None,
                    input_device_index=self.input_device_index,
                    output_device_index=self.output_device_index,
                    frames_per_buffer=self._chunksize,
                    stream_callback=self._audiocallback,
                    start=False)
        self._head = 0
        
        # outbuffer
        size = self.nb_channel * self._chunksize * np.dtype(self.format).itemsize
        self.enmpty_outputbuffer = b'\x00' * size
        self.out_queue = collections.deque()
        self.lock = Mutex()
        
        if self.output_device_index is not None:
            self.thread = ThreadPollInput(self.input)
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
            self._head += self._chunksize
            self.output.send(self._head, in_data)
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
