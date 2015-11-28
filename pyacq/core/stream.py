import zmq
import numpy as np
import random
import string
import weakref
try:
    import blosc
    HAVE_BLOSC = True
except ImportError:
    HAVE_BLOSC = False

from .sharedarray import SharedArray
from .rpc import ObjectProxy


default_stream = dict(protocol='tcp', interface='127.0.0.1', port='*',
                        transfermode='plaindata', streamtype='analogsignal',
                        dtype='float32', shape=(-1, 1), timeaxis = 0, 
                        compression ='', scale = None, offset = None, units = '',
                        sample_rate = 1.,)


common_doc = """
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
    timeaxis: int
        The index of the axis that represents time within a single data chunk, or
        -1 if the chunk lacks this axis (in this case, each chunk represents exactly one
        timepoint).
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

    

class OutputStream(object):
    """Class for streaming data to an InputStream.
    
    Streams allow data to be sent between objects that may exist on different
    threads, processes, or machines. They offer a variety of transfer methods
    including TCP for remote connections and IPC for local connections.
    """
    def __init__(self, spec={}, node=None, name=None):
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
        
        """+common_doc
        
        self.params = dict(default_stream)
        self.params.update(self.spec)
        self.params.update(kargs)
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
        
        if self.params['transfermode'] == 'plaindata':
            self.sender = PlainDataSender(self.socket, self.params)
        elif self.params['transfermode'] == 'sharedarray':
            self.sender = SharedArraySender(self.socket, self.params)

        self.configured = True
        if self.node and self.node():
            self.node().after_output_configure(self.name)

    def send(self, index, data):
        """Send a data chunk and its frame index.
        
        Parameters
        ----------
        index: int
            The absolute sample index. If the chunk contains multiple samples,
            then this is the index of the last sample.
        data: np.ndarray or bytes
            The chunk of data to send.
        """
        self.sender.send(index, data)

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
    def __init__(self, spec={}, node=None, name=None):
        self.configured = False
        self.spec = spec
        if node is not None:
            self.node = weakref.ref(node)
        else:
            self.node = None
        self.name = name
    
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

        context = zmq.Context.instance()
        self.socket = context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')
        #~ self.socket.setsockopt(zmq.DELAY_ATTACH_ON_CONNECT,1)
        self.socket.connect(self.url)
        
        if self.params['transfermode'] == 'plaindata':
            self.receiver = PlainDataReceiver(self.socket, self.params)
        elif self.params['transfermode'] == 'sharedarray':
            self.receiver = SharedArrayReceiver(self.socket, self.params)
        else:
            raise
        
        self.connected = True
        if self.node and self.node():
            self.node().after_input_connect(self.name)        
    
    def poll(self, timeout=None):
        """Poll the socket of input stream.
        """
        return self.socket.poll(timeout=timeout)
    
    def recv(self):
        """
        Receive a chunk of data.
        
        Returns:
        ----
        index: int
            The absolute sample index. If the chunk contains multiple samples,
            then this is the index of the last sample.
        data: np.ndarray or bytes
            The received chunk of data.
            If the stream uses `transfermode='sharedarray'`, then the data is 
            returned as None and you must use `InputStream.get_array_slice(index, length)`
            to read from the shared array.

        """
        return self.receiver.recv()

    def close(self):
        """Close the Input.
        
        This closes the socket.
        
        """
        self.receiver.close()
        self.socket.close()
        del self.socket
    
    def get_array_slice(self, index, length):
        """Return a slice from the shared memory array, if this stream uses
        `transfermode='sharedarray'`.
        
        Parameters
        ----------
        index : int
            The starting index to read from the array.
        length : int or None
            The lengfth of the slice to read from the array. This value may not
            be greater than the ring size. If length is None, then return the
            last chunk received.
        """
        # assert self.params['transfermode'] == 'sharedarray', 'For sharedarray only'
        if length is None:
            return self.receiver.get_array_slice(index, self.receiver.last_chunk_size)
        
        return self.receiver.get_array_slice(index, length)


class PlainDataSender:
    """
    Helper class to send data in 2 parts with a zmq socket:
    
    * index
    * data
    
    The data parts can be compressed.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        self.copy = self.params['protocol'] == 'inproc'
        
        self.funcs = []
        # compression
        if self.params['compression'] == '':
            pass
        elif self.params['compression'] == 'blosc-blosclz':
            # cname for ['blosclz', 'lz4', 'lz4hc', 'snappy', 'zlib']
            self.funcs.append(self.compress_blosclz)
        elif self.params['compression'] == 'blosc-lz4':
            self.funcs.append(self.compress_blosclz4)        
    
    def compress_blosclz(self, index, data):
        assert HAVE_BLOSC, "Cannot use blosclz compression; blosc package is not importable."
        data = blosc.pack_array(data, cname='blosclz')
        return index, data
    
    def compress_blosclz4(self, index, data):
        assert HAVE_BLOSC, "Cannot use blosclz4 compression; blosc package is not importable."
        data = blosc.pack_array(data, cname='lz4')
        return index, data
    
    def send(self, index, data):
        # TODO deal when data is nparray and self.copy is False and a.flags['C_CONTIGUOUS']=False
        for f in self.funcs:
            index, data = f(index, data)
        self.socket.send_multipart([np.int64(index), data], copy=self.copy)
    
    def close(self):
        pass


class PlainDataReceiver:
    """
    Helper class to receive data in 2 parts.
    
    See PlainDataSender.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        
        if self.params['compression'] == '':
            self.func = self._numpy_fromstring
        elif self.params['compression'] in ['blosc-blosclz', 'blosc-lz4']:
            self.func = self._uncompress_blosc
    
    def recv(self):
        m0,m1 = self.socket.recv_multipart()
        index = np.fromstring(m0, dtype='int64')[0]
        return self.func(index, m1)
        
    def close(self):
        pass

    def _numpy_fromstring(self, index, data):
        data = np.frombuffer(data, dtype=self.params['dtype']).reshape(self.params['shape'])
        return index, data
    
    def _uncompress_blosc(self, index, data):
        data = blosc.unpack_array(data)
        return index, data


class SharedArraySender:
    """
    Helper class to share data in a SharedArray and send in the socket only the index.
    The SharedArray can have any size larger than one chunk.
    
    This is useful for a Node that needs to access older chunks.
    
    Be careful to correctly set the timeaxis (concatenation axis).
    
    Note that on Unix using plaindata+inproc can be faster.
    """
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        #~ self.copy = self.params['protocol'] == 'inproc'
        self.copy = False
        
        assert 'ring_buffer_method' in params, 'ring_buffer_method not in params for sharedarray'
        assert 'sharedarray_shape' in params, 'sharedarray_shape not in params for sharedarray'
        
        if self.params['ring_buffer_method'] == 'single':
            #~ self.funcs.append(self._copy_to_sharray_single)
            self.func = self._copy_to_sharray_single
        elif self.params['ring_buffer_method'] == 'double':
            #~ self.funcs.append(self._copy_to_sharray_double)
            self.func = self._copy_to_sharray_double
        self._index = 0
        
        # prepare SharedArray
        self._timeaxis = self.params['timeaxis']
        self._ring_size = self.params['sharedarray_shape'][self._timeaxis]
        sharedarray_shape = list(self.params['sharedarray_shape'])
        self._ndim = len(sharedarray_shape)
        assert self._ndim==len(self.params['shape']), 'sharedarray_shape and shape must coherent!'
        if self.params['ring_buffer_method'] == 'double':
            sharedarray_shape[self._timeaxis] = self._ring_size*2
        self._sharedarray = SharedArray(shape=sharedarray_shape, dtype=self.params['dtype'])
        self.params['shm_id'] = self._sharedarray.shm_id
        self._numpyarr = self._sharedarray.to_numpy()

    def send(self, index, data):
        self.func(index, data)

    def close(self):
        self._sharedarray.close()

    def _copy_to_sharray_single(self, index, data):
        assert data.shape[self._timeaxis]<self._ring_size, 'The chunk is too big for the buffer {} {}'.format(data.shape, self._numpyarr.shape)
        head = index % self._ring_size
        tail = self._index%self._ring_size
        if head>tail:
            # 1 chunks
            sl = [slice(None)] * self._ndim
            sl[self._timeaxis] = slice(tail, head)
            self._numpyarr[sl] = data
        else:
            # 2 chunks : because end of the ring
            size1 = self._ring_size-tail
            size2 = data.shape[self._timeaxis] - size1
            
            # part1
            sl1 = [slice(None)] * self._ndim 
            sl1[self._timeaxis] = slice(tail, None)
            sl2 = [slice(None)] * self._ndim 
            sl2[self._timeaxis] = slice(None, size1)
            self._numpyarr[sl1] = data[sl2]
            
            # part2
            sl3 = [slice(None)] * self._ndim
            sl3[self._timeaxis] = slice(None, size2)
            sl4 = [slice(None)] * self._ndim
            sl4[self._timeaxis] = slice(-size2, None)
            self._numpyarr[sl3] = data[sl4]
        
        self.socket.send(np.int64(index), copy=self.copy)
        self._index += data.shape[self._timeaxis]


    def _copy_to_sharray_double(self, index, data):
        head = index % self._ring_size
        tail = self._index%self._ring_size
        if head>tail:
            sl = [slice(None)] * self._ndim
            sl[self._timeaxis] = slice(tail, head)
            # 1 chunk
            self._numpyarr[sl] = data
            # 1 same chunk
            sl[self._timeaxis] = slice(tail+self._ring_size, head+self._ring_size)
            self._numpyarr[sl] = data
            
        else:
            size1 = self._ring_size-tail
            size2 = data.shape[self._timeaxis] - size1
            
            # 1 full chunks continuous
            sl = [slice(None)] * self._ndim 
            sl[self._timeaxis] = slice(tail, head+self._ring_size)
            self._numpyarr[sl] = data
            
            # part1 : in the second ring
            if size1>0:
                sl1 = [slice(None)] * self._ndim 
                sl1[self._timeaxis] = slice(tail+self._ring_size, None)
                sl2 = [slice(None)] * self._ndim 
                sl2[self._timeaxis] = slice(None, size1)
                self._numpyarr[sl1] = data[sl2]
            
            # part2 : in the first ring
            if size2:
                sl3 = [slice(None)] * self._ndim
                sl3[self._timeaxis] = slice(None, size2)
                sl4 = [slice(None)] * self._ndim
                sl4[self._timeaxis] = slice(-size2, None)
                self._numpyarr[sl3] = data[sl4]
            
        self.socket.send(np.int64(index), copy=self.copy)
        self._index += data.shape[self._timeaxis]
 


class SharedArrayReceiver:
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params

        self._timeaxis = self.params['timeaxis']
        self._ring_size = self.params['sharedarray_shape'][self._timeaxis]
        sharedarray_shape = list(self.params['sharedarray_shape'])
        self._ndim = len(sharedarray_shape)
        assert self._ndim==len(self.params['shape']), 'sharedarray_shape and shape must coherent!'
        if self.params['ring_buffer_method'] == 'double':
            sharedarray_shape[self._timeaxis] = self._ring_size*2
        self._sharedarray = SharedArray(shape=sharedarray_shape, dtype=self.params['dtype'], shm_id=self.params['shm_id'])
        self._numpyarr = self._sharedarray.to_numpy()
        self.last_chunk_size = None
        self.last_index = 0

    def recv(self):
        m0 = self.socket.recv()
        index = np.fromstring(m0, dtype='int64')[0]
        self.last_chunk_size = index - self.last_index
        self.last_index = index
        return index, None

    def get_array_slice(self, index, length):
        assert length<self._ring_size, 'The ring size is too small {} {}'.format(self._ring_size, length)
        if self.params['ring_buffer_method'] == 'double':
            i2 = index%self._ring_size + self._ring_size
            i1 = i2 - length
            sl = [slice(None)] * self._ndim 
            sl[self._timeaxis] = slice(i1,i2)
            return self._numpyarr[sl]
        elif self.params['ring_buffer_method'] == 'single':
            raise(NotImplementedError)
    
    def close(self):
        pass
