import random
import string
import zmq
import numpy as np
import weakref

from .ringbuffer import RingBuffer
from .streamhelpers import all_transfermodes
from ..rpc import ObjectProxy


default_stream = dict(
    protocol='tcp',
    interface='127.0.0.1',
    port='*',
    transfermode='plaindata',
    streamtype='analogsignal',
    dtype='float32',
    shape=(-1, 1),
    axisorder=None,
    buffer_size=0,
    compression='',
    scale=None,
    offset=None,
    units='',
    sample_rate=1.,
    double=False,#make sens only for transfermode='sharemem',
    fill=None,
)


class OutputStream(object):
    """Class for streaming data to an InputStream.
    
    Streams allow data to be sent between objects that may exist on different
    threads, processes, or machines. They offer a variety of transfer methods
    including TCP for remote connections and IPC for local connections.
    """
    def __init__(self, spec=None, node=None, name=None):
        spec = {} if spec is None else spec
        self.last_index = 0
        self.configured = False
        self.spec = spec  # this is a priori stream params, and must be change when Node.configure
        if node is not None:
            self.node = weakref.ref(node)
        else:
            self.node = None
        self.name = name
    
    def configure(self, **kargs):
        """
        Configure the output stream.
        
        Parameters
        ----------
        protocol : 'tcp', 'udp', 'inproc' or 'inpc' (linux only)
            The type of protocol used for the zmq.PUB socket
        interface : str
            The bind adress for the zmq.PUB socket
        port : str
            The port for the zmq.PUB socket
        transfermode: 'plain_data', 'sharedarray', (not done 'shared_cuda_buffer' or 'share_opencl_buffer')
            The method used for data transfer:
            * 'plain_data': data are sent over a plain socket in two parts: (frame index, data).
            * 'sharedarray': data are stored in shared memory in a ring buffer and the current frame index is sent over the socket.
            * 'shared_cuda_buffer': data are stored in shared Cuda buffer and the current frame index is sent over the socket.
            * 'share_opencl_buffer': data are stored in shared OpenCL buffer and the current frame index is sent over the socket.
        streamtype: 'analogsignal', 'digitalsignal', 'event' or 'image/video'
            The type of data to be transferred.
        dtype: str ('float32','float64', [('r', 'uint16'), ('g', 'uint16'), , ('b', 'uint16')], ...)
            The numpy.dtype of the data buffer. It can be a composed dtype for event or images.
        shape: list
            The shape of each data frame. If the stream will send chunks of variable length,
            then use -1 for the unknown dimension.
            * For ``streamtype=image``, the shape should be (-1, H, W), (n_frames, H, W), or (H, W).
            * For ``streamtype=analogsignal`` the shape should be (n_samples, n_channels) or (-1, n_channels)
        compression: '', 'blosclz', 'blosc-lz4', 'mp4', 'h264'
            The compression for the data stream. The default uses no compression.
        scale: float
            An optional scale factor + offset to apply to the data before it is sent over the stream.
            ``output = offset + scale * input``
        offset:
            See scale.
        units: str
            Units of the stream data. Mainly used for 'analogsignal'.
        sample_rate: float or None
            Sample rate of the stream in Hz.
        sample_interval: float or None
        sharedarray_shape: tuple
            Shape of the SharedArray when using `transfermode = 'sharedarray'`.
        ring_buffer_method: 'double' or 'single'
            Method for the ring buffer when using `transfermode = 'sharedarray'`:
            * 'single': a standard ring buffer.
            * 'double': 2 ring buffers concatenated together. This ensures that
            a continuous chunk exists in memory regardless of the sample position.
            Note that, The ring buffer is along `timeaxis` for each case. And in case, of 'double', concatenated axis is also `timeaxis`.
        shm_id : str or int (depending on platform)
            id of the SharedArray when using `transfermode = 'sharedarray'`.

        """
        
        self.params = dict(default_stream)
        self.params.update(self.spec)
        for k in kargs:
            if k in self.spec:
                assert kargs[k]==self.spec[k], \
                    'Cannot configure {}={}; already in fixed in self.spec {}={}'.format(k, kargs[k], k, self.spec[k])
        self.params.update(kargs)
        
        shape = self.params['shape']
        assert shape[0] == -1 or shape[0] > 0, "First element in shape must be -1 or > 0."
        for i in range(1, len(shape)):
            assert shape[i] > 0, "Shape index %d must be > 0." % i
        
        if self.params['protocol'] in ('inproc', 'ipc'):
            pipename = u'pyacq_pipe_'+''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(24))
            self.params['interface'] = pipename
            self.url = '{protocol}://{interface}'.format(**self.params)
        else:
            self.url = '{protocol}://{interface}:{port}'.format(**self.params)
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(self.url)
        self.addr = self.socket.getsockopt(zmq.LAST_ENDPOINT).decode()
        self.port = self.addr.rpartition(':')[2]
        self.params['port'] = self.port
        
        transfermode = self.params['transfermode']
        if transfermode not in all_transfermodes:
            raise ValueError("Unsupported transfer mode '%s'" % transfermode)
        sender_class = all_transfermodes[transfermode][0]
        self.sender = sender_class(self.socket, self.params)

        self.configured = True
        if self.node and self.node():
            self.node().after_output_configure(self.name)

    def send(self, data, index=None, **kargs):
        """Send a data chunk and its frame index.
        
        Parameters
        ----------
        index: int
            The absolute sample index. This is the index of the last sample + 1.
        data: np.ndarray or bytes
            The chunk of data to send.
        """
        if index is None:
            index = self.last_index + data.shape[0]
        self.last_index = index
        self.sender.send(index, data, **kargs)

    def close(self):
        """Close the output.
        
        This closes the socket and releases shared memory, if necessary.
        """
        self.sender.close()
        self.socket.close()
        del self.socket
        del self.sender


class InputStream(object):
    """Class for streaming data from an OutputStream.
    
    Streams allow data to be sent between objects that may exist on different
    threads, processes, or machines. They offer a variety of transfer methods
    including TCP for remote connections and IPC for local connections.
    """
    def __init__(self, spec=None, node=None, name=None):
        self.spec = {} if spec is None else spec
        self.configured = False
        if node is not None:
            self.node = weakref.ref(node)
        else:
            self.node = None
        self.name = name
        self.buffer = None
        self._own_buffer = False  # whether InputStream should populate buffer
    
    def connect(self, output):
        """Connect an output to this input.
        
        Any data send over the stream using `output.send()` can be retrieved
        using `input.recv()`.
        """
        if isinstance(output, dict):
            self.params = output
        elif isinstance(output, OutputStream):
            self.params = output.params
        elif isinstance(output, ObjectProxy):
            self.params = output.params._get_value()
        else:
            raise TypeError("Invalid type for stream: %s" % type(output))
            
        if self.params['protocol'] in ('inproc', 'ipc'):
            self.url = '{protocol}://{interface}'.format(**self.params)
        else:
            self.url = '{protocol}://{interface}:{port}'.format(**self.params)
            
        # allow some keys in self.spec to override self.params
        readonly_params = ['protocol', 'transfermode', 'shape', 'dtype']
        for k,v in self.spec.items():
            if k in readonly_params and v != self.params[k]:
                raise ValueError("InputStream parameter %s=%s does not match connected output %s=%s." %
                                 (k, v, k, self.params[k]))
            else:
                self.params[k] = v

        context = zmq.Context.instance()
        self.socket = context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')
        #~ self.socket.setsockopt(zmq.DELAY_ATTACH_ON_CONNECT,1)
        self.socket.connect(self.url)
        
        transfermode = self.params['transfermode']
        if transfermode not in all_transfermodes:
            raise ValueError("Unsupported transfer mode '%s'" % transfermode)
        receiver_class = all_transfermodes[transfermode][1]
        self.receiver = receiver_class(self.socket, self.params)
        
        self.connected = True
        if self.node and self.node():
            self.node().after_input_connect(self.name)        
    
    def poll(self, timeout=None):
        """Poll the socket of input stream.
        """
        return self.socket.poll(timeout=timeout)
    
    def recv(self, **kargs):
        """
        Receive a chunk of data.
        
        Returns:
        ----
        index: int
            The absolute sample index. This is the index of the last sample + 1.
        data: np.ndarray or bytes
            The received chunk of data.
            If the stream uses `transfermode='sharedarray'`, then the data is 
            returned as None and you must use `InputStream.get_array_slice(index, length)`
            to read from the shared array or InputStream.recv(with_data=True) to get the last
            chunk.

        """
        index, data = self.receiver.recv(**kargs)
        if self._own_buffer and data is not None and self.buffer is not None:
            self.buffer.new_chunk(data, index=index)
        return index, data

    def close(self):
        """Close the Input.
        
        This closes the socket.
        
        """
        self.receiver.close()
        self.socket.close()
        del self.socket
    
    def __getitem__(self, *args):
        """Return a data slice from the RingBuffer attached to this InputStream.
        
        If no RingBuffer is attached, raise an exception. See ``set_buffer()``.
        """
        if self.buffer is None:
            raise TypeError("No ring buffer configured for this InputStream.")
        return self.buffer.__getitem__(*args)
    
    def get_data(self, *args, **kargs):
        """
        Return a segment of the RingBuffer attached to this InputStream.
        
        If no RingBuffer is attached, raise an exception. See ``set_buffer()``.
        """
        if self.buffer is None:
            raise TypeError("No ring buffer configured for this InputStream.")
        return self.buffer.get_data(*args, **kargs)
    
    #~ def set_buffer(self, size=None, double=True, axisorder=None):
    def set_buffer(self, size=None, double=True, axisorder=None, shmem=None, fill=None):
        """Ensure that this InputStream has a RingBuffer at least as large as 
        *size* and with the specified double-mode and axis order.
        
        If necessary, this will attach a new RingBuffer to the stream and remove
        any existing buffer.
        """
        # first see if we already have a buffer that meets requirements
        bufs = []
        if self.buffer is not None:
            bufs.append((self.buffer, self._own_buffer))
        if self.receiver.buffer is not None:
            bufs.append((self.receiver.buffer, False))
        for buf, own in bufs:
            if buf.shape[0] >= size and buf.double == double and (axisorder is None or all(buf.axisorder == axisorder)):
                self.buffer = buf
                self._own_buffer = own
                return
            
        # attach a new buffer
        shape = (size,) + tuple(self.params['shape'][1:])
        dtype = self.params['dtype']
        #~ self.buffer = RingBuffer(shape=shape, dtype=dtype, double=double, axisorder=axisorder)
        self.buffer = RingBuffer(shape=shape, dtype=dtype, double=double, axisorder=axisorder, shmem=shmem, fill=fill)
        self._own_buffer = True
