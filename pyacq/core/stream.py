import struct
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

from .sharedarray import SharedMem, SharedArray
from .rpc import ObjectProxy


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
    sample_rate=1.
)


class OutputStream(object):
    """Class for streaming data to an InputStream.
    
    Streams allow data to be sent between objects that may exist on different
    threads, processes, or machines. They offer a variety of transfer methods
    including TCP for remote connections and IPC for local connections.
    """
    def __init__(self, spec=None, node=None, name=None):
        spec = {} if spec is None else spec
        self.last_index = -1
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
        
        if self.params['transfermode'] == 'plaindata':
            self.sender = PlainDataSender(self.socket, self.params)
        elif self.params['transfermode'] == 'sharedarray':
            self.sender = SharedArraySender(self.socket, self.params)
        elif self.params['transfermode'] == 'sharedmem':
            self.sender = SharedMemSender(self.socket, self.params)

        self.configured = True
        if self.node and self.node():
            self.node().after_output_configure(self.name)

    def send(self, data, index=None, **kargs):
        """Send a data chunk and its frame index.
        
        Parameters
        ----------
        index: int
            The absolute sample index. If the chunk contains multiple samples,
            then this is the index of the last sample.
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
        
        if self.params['transfermode'] == 'plaindata':
            self.receiver = PlainDataReceiver(self.socket, self.params)
        elif self.params['transfermode'] == 'sharedarray':
            self.receiver = SharedArrayReceiver(self.socket, self.params)
        elif self.params['transfermode'] == 'sharedmem':
            self.receiver = SharedMemReceiver(self.socket, self.params)
        else:
            raise ValueError('Unsupported transfermode "%s"' % self.params['transfermode'])
        
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
            The absolute sample index. If the chunk contains multiple samples,
            then this is the index of the last sample.
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
    
    def get_array_slice(self, index, length):
        """Return a slice from the ring buffer that accumulates data.
        
        Requires `bufferSize` to be specified at initialization.
        
        Parameters
        ----------
        index : int
            The starting index to read from the array.
        length : int or None
            The lengfth of the slice to read from the array. This value may not
            be greater than the ring size. If length is None, then return the
            last chunk received.
        """
        if length is None:
            length = self.receiver.last_chunk_size
        
        return self[index:index+length]

    def __getitem__(self, *args):
        if self.buffer is None:
            raise TypeError("No ring buffer configured for this InputStream.")
        return self.buffer.__getitem__(*args)

    def set_buffer(self, size=None, double=True, axisorder=None):
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
        self.buffer = RingBuffer(shape=shape, dtype=dtype, double=double, axisorder=axisorder)
        self._own_buffer = True


class DataSender:
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        self.funcs = []

    def send(self, index, data):
        raise NotImplementedError()
    
    def close(self):
        pass


class PlainDataSender(DataSender):
    """
    Helper class to send data in 2 parts with a zmq socket:
    
    * index
    * data
    
    The data parts can be compressed.
    """
    def send(self, index, data):
        # optional pre-processing before send
        if isinstance(data, np.ndarray):
            for f in self.funcs:
                index, data = f(index, data)
                
        # serialize
        dtype = data.dtype
        shape = data.shape
        buf, offset, strides = decompose_array(data)
        
        # compress
        comp = self.params['compression']
        if comp.startswith('blosc-'):
            assert HAVE_BLOSC, "Cannot use blosclz4 compression; blosc package is not importable."
            buf = blosc.compress(buf, data.itemsize, cname=comp[6:])
        elif comp != '':
            raise ValueError("Unknown compression method '%s'" % comp)
        
        # Pack and send
        stat = struct.pack('!' + 'Q' * (3+len(shape)) + 'q' * len(strides), len(shape), index, offset, *(shape + strides))
        copy = self.params.get('copy', False)
        self.socket.send_multipart([stat, buf], copy=copy)


class DataReceiver:
    def __init__(self, socket, params):
        self.socket = socket
        self.params = params
        self.buffer = None
            
    def recv(self):
        raise NotImplementedError()
    
    def close(self):
        pass
    
    

class PlainDataReceiver(DataReceiver):
    """
    Helper class to receive data in 2 parts.
    
    See PlainDataSender.
    """
    def __init__(self, socket, params):
        DataReceiver.__init__(self, socket, params)
    
    def recv(self):
        # receive and unpack structure
        stat, data = self.socket.recv_multipart()
        ndim = struct.unpack('!Q', stat[:8])[0]
        stat = struct.unpack('!' + 'Q' * (ndim + 2) + 'q' * ndim, stat[8:])
        index = stat[0]
        offset = stat[1]
        shape = stat[2:2+ndim]
        strides = stat[-ndim:]
        
        # uncompress
        comp = self.params['compression']
        if comp.startswith('blosc-'):
            assert HAVE_BLOSC, "Cannot use blosc decompression; blosc package is not importable."
            data = blosc.decompress(data)
        elif comp != '':
            raise ValueError("Unknown compression method '%s'" % comp)
        
        # convert to array
        dtype = self.params['dtype']
        data = np.ndarray(buffer=data, shape=shape,
                          strides=strides, offset=offset, dtype=dtype)        
        return index, data


class SharedMemSender(DataSender):
    """
    """
    def __init__(self, socket, params):
        DataSender.__init__(self, socket, params)
        self.size = self.params['buffer_size']
        dtype = np.dtype(self.params['dtype'])
        shape = (self.size,) + self.params['shape'][1:]
        self._buffer = RingBuffer(shape=shape, dtype=self.params['dtype'],
                                  shmem=True, axisorder=self.params['axisorder'])
        self.params['shm_id'] = self._buffer.shm_id
    
    def send(self, index, data):
        assert data.dtype == self.params['dtype']
        shape = data.shape
        if self.params['shape'][0] != -1:
            assert shape == self.params['shape']
        else:
            assert shape[1:] == self.params['shape'][1:]
 
        self._buffer.new_chunk(data, index)
        
        stat = struct.pack('!' + 'Q' * (2+len(shape)), len(shape), index, *shape)
        self.socket.send_multipart([stat])


class SharedMemReceiver(DataReceiver):
    def __init__(self, socket, params):
        # init data receiver with no ring buffer; we will implement our own from shm.
        DataReceiver.__init__(self, socket, params)

        self.size = self.params['buffer_size']
        shape = (self.size,) + self.params['shape'][1:]
        self.buffer = RingBuffer(shape=shape, dtype=self.params['dtype'],
                                  shmem=self.params['shm_id'], axisorder=self.params['axisorder'])

    def recv(self):
        stat = self.socket.recv_multipart()[0]
        ndim = struct.unpack('!Q', stat[:8])[0]
        stat = struct.unpack('!' + 'Q' * (ndim + 1), stat[8:])
        index = stat[0]
        shape = stat[1:1+ndim]
        data = self.buffer[index+1-shape[0]:index+1]
        return index, data


class RingBuffer:
    """Class that collects data as it arrives from an InputStream and writes it
    into a single- or double-ring buffer.
    
    This allows the user to request the concatenated history of data
    received by the stream, up to a predefined length. Double ring buffers
    allow faster, copyless reads at the expense of doubled write time and memory
    footprint.
    """
    def __init__(self, shape, dtype, double=True, shmem=None, fill=None, axisorder=None):
        self.double = double
        self.shape = shape
        # order of axes as written in memory. This does not affect the shape of the 
        # buffer as seen by the user, but can be used to make sure a specific axis
        # is contiguous in memory.
        if axisorder is None:
            axisorder = np.arange(len(shape))
        self.axisorder = np.array(axisorder)
        
        shape = (shape[0] * (2 if double else 1),) + shape[1:]
        nativeshape = np.array(shape)[self.axisorder]
        
        # initialize int buffers with 0 and float buffers with nan
        if fill is None:
            fill = 0 if np.dtype(dtype).kind in 'ui' else np.nan
        self._filler = fill
        
        if shmem is None:
            self.buffer = np.empty(nativeshape, dtype=dtype).transpose(np.argsort(axisorder))
            self.buffer[:] = self._filler
            self._indexes = np.zeros((2,), dtype='int64')
            self._shmem = None
            self.shm_id = None
        else:
            size = np.product(shape) * np.dtype(dtype).itemsize + 16
            if shmem is True:
                # create new shared memory buffer
                self._shmem = SharedMem(nbytes=size)
            else:
                self._shmem = SharedMem(nbytes=size, shm_id=shmem)
            self.buffer = self._shmem.to_numpy(offset=16, dtype=dtype, shape=nativeshape).transpose(np.argsort(axisorder))
            self._indexes = self._shmem.to_numpy(offset=0, dtype='int64', shape=(2,))
            self.shm_id = self._shmem.shm_id
        
        self.dtype = self.buffer.dtype
        
        if shmem in (None, True):
            # Index of last writable sample. This value is used to determine which
            # buffer indices map to which data indices (where buffer indices wrap
            # around to 0, but data indices always increase as data arrives).
            self._set_write_index(-1)
            # Index of last written sample. This is used to determine how much of
            # the buffer is *valid* for reading.
            self._set_read_index(-1)
        
        # Note: read_index and write_index are defined independently to avoid
        # race condifions with processes reading and writing from the same
        # shared memory simultaneously. When new data arrives:
        #   1. write_index is increased to indicate that the buffer has advanced
        #      and some old data is no longer valid
        #   2. new data is written over the old buffer data
        #   3. read_index is increased to indicate that the new data is now
        #      readable

        #
        #              write_index+1-bsize   break_index     read_index       write_index
        #              |                     |               |                |
        #    ..........<.....................|...............>................v
        #                                    |
        #              [           readable area             ][ writable area ]
        #                                    |
        #                                    |  [........]           read without copy
        #                        [........]  |                       read without copy
        #                               [....|......]                read with copy
        # 
        
    def last_index(self):
        return self._read_index

    def first_index(self):
        return self._read_index + 1 - self.shape[0]

    @property
    def _write_index(self):
        return self._indexes[1]

    @property
    def _read_index(self):
        return self._indexes[0]

    def _set_write_index(self, i):
        # what kind of protection do we need here?
        self._indexes[1] = i

    def _set_read_index(self, i):
        # what kind of protection do we need here?
        self._indexes[0] = i

    def new_chunk(self, data, index=None):
        dsize = data.shape[0]
        bsize = self.shape[0]
        if dsize > bsize:
            raise ValueError("Data chunk size %d is too large for ring "
                            "buffer of size %d." % (dsize, bsize))
        if data.dtype != self.dtype:
            raise TypeError("Data has incorrect dtype %s (buffer requires %s)" %
                            (data.dtype, self.dtype))
        
        # by default, index advances by the size of the chunk
        if index is None:
            index = self._write_index + dsize
        
        assert dsize <= index - self._write_index, ("Data size is %d, but index "
                                                    "only advanced by %d." % 
                                                    (dsize, index-self._write_index)) 

        revert_inds = [self._read_index, self._write_index]
        try:
            # advance write index. This immediately prevents other processes from
            # accessing memory that is about to be overwritten.
            self._set_write_index(index)
            
            # decide if any skipped data needs to be filled in
            fill_start = max(self._read_index + 1, self._write_index + 1 - bsize)
            fill_stop = self._write_index + 1 - dsize
            
            if fill_stop > fill_start:
                # data was skipped; fill in missing regions with 0 or nan.
                self._write(fill_start, fill_stop, self._filler)
                revert_inds[1] = fill_stop-1
                
            self._write(self._write_index + 1 - dsize, self._write_index + 1, data)
                
            self._set_read_index(index)
        except:
            # If there is a failure writing data, revert read/write pointers
            self._set_read_index(revert_inds[0])
            self._set_write_index(revert_inds[1])
            raise

    def _write(self, start, stop, value):
        # get starting index
        bsize = self.shape[0]
        dsize = stop - start
        i = start % bsize
        
        if self.double:
            self.buffer[i:i+dsize] = value
            i += bsize
        
        if i + dsize <= self.buffer.shape[0]:
            self.buffer[i:i+dsize] = value
        else:
            n = self.buffer.shape[0]-i
            self.buffer[i:] = value[:n]
            self.buffer[:dsize-n] = value[n:]
        
    def __getitem__(self, item):
        if isinstance(item, tuple):
            first = item[0]
            rest = (slice(None),) + item[1:]
        else:
            first = item
            rest = None
        
        if isinstance(first, (int, np.integer)):
            start = self._interpret_index(first)
            stop = start + 1
            data = self.get_data(start, stop)[0]
            if rest is not None:
                data = data[rest[1:]]
        elif isinstance(first, slice):
            start, stop, step = self._interpret_index(first)
            data = self.get_data(start, stop)[::step]
            if rest is not None:
                data = data[rest]
        else:
            raise TypeError("Invalid index type %s" % type(first))
        
        return data

    def get_data(self, start, stop, copy=False, join=True):
        """Return a segment of the ring buffer.
        
        Parameters
        ----------
        start : int
            The starting index of the segment to return.
        stop : int
            The stop index of the segment to return (the sample at this index
            will not be included in the returned data)
        copy : bool
            If True, then a copy of the data is returned to ensure that modifying
            the data will not affect the ring buffer. If False, then a reference to
            the buffer will be returned if possible. Default is False.
        join : bool
            If True, then a single contiguous array is returned for the entire
            requested segment. If False, then two separate arrays are returned
            for the beginning and end of the requested segment. This can be
            used to avoid an unnecessary copy when the buffer has double=False
            and the caller does not require a contiguous array.
        """
        first, last = self.first_index(), self.last_index()+1
        if start < first or stop > last:
            raise IndexError("Requested segment (%d, %d) is out of bounds for ring buffer. "
                             "Current bounds are (%d, %d)." % (start, stop, first, last))
        
        bsize = self.shape[0]
        copied = False
        
        if self.double:
            start_ind = start % bsize
            stop_ind = start_ind + (stop - start)
            data = self.buffer[start_ind:stop_ind]
        else:
            break_index = (self._write_index + 1) - ((self._write_index + 1) % bsize)
            if (start < break_index) == (stop <= break_index):
                start_ind = start % bsize
                stop_ind = start_ind + (stop - start)
                data = self.buffer[start_ind:stop_ind]
            else:
                # need to reconstruct from two pieces
                newshape = np.array((stop-start,) + self.shape[1:])[self.axisorder]
                a = self.buffer[start%bsize:]
                b = self.buffer[:stop%bsize]
                if join is False:
                    if copy is True:
                        return (a.copy(), b.copy())
                    else:
                        return (a, b)
                else:
                    data = np.empty(newshape, self.buffer.dtype).transpose(np.argsort(self.axisorder))
                    data[:break_index-start] = a
                    data[break_index-start:] = b
                    copied = True
        
        if copy and not copied:
            data = data.copy()
            
        if join:
            return data
        else:
            empty = np.empty((0,) + data.shape[1:], dtype=data.dtype)
            return data, empty

    def _interpret_index(self, index):
        """Return normalized index, accounting for negative and None values.
        Also check that the index is readable.
        
        Slices are returned such that start,stop are swapped and shifted -1 if
        the step is negative. This makes it possible to collect the result in
        the forward direction and handle the step later.
        """
        start_index = self._write_index + 1 - self.shape[0]
        if isinstance(index, (int, np.integer)):
            if index < 0:
                index += self._read_index + 1
            if index > self._read_index or index < start_index:
                raise IndexError("Index %d is out of bounds for ring buffer [%d, %d]" %
                                 (index, start_index, self._read_index))
            return index
        elif isinstance(index, slice):
            start, stop, step = index.start, index.stop, index.step
            
            # Handle None and negative steps
            if step is None:
                step = 1
            if step < 0:
                start, stop = stop, start
                
            # Interpret None and negative indices
            if start is None:
                start = start_index
            else:
                if start < 0:
                    start += self._read_index + 1
                if step < 0:
                    start += 1 
                
            if stop is None:
                stop = self._read_index + 1
            else:
                if stop < 0:
                    stop += self._read_index + 1
                if step < 0:
                    stop += 1
                
            # Bounds check.
            # Perhaps we could clip the returned data like lists/arrays do,
            # but in this case the feedback is likely to be useful to the user.
            if stop > self._read_index+1 or stop < start_index:
                raise IndexError("Stop index %d is out of bounds for ring buffer [%d, %d]" %
                                 (stop, start_index, self._read_index))
            if start > self._read_index or start < start_index:
                raise IndexError("Start index %d is out of bounds for ring buffer [%d, %d]" %
                                 (start, start_index, self._read_index))
            return start, stop, step
        else:
            raise TypeError("Invalid index %s" % index)
    

def axis_order_copy(data, out=None):
    """Copy *data* such that the result is contiguous, but preserves the axis order
    in memory.
    
    If *out* is provided, then write the copy into that array instead creating
    a new one. *out* must be an array of the same dtype and size, with ndim=1.
    """
    # transpose to natural order
    order = np.argsort(np.abs(data.strides))[::-1]    
    data = data.transpose(order)
    # reverse axes if needed
    ind = tuple((slice(None, None, -1) if data.strides[i] < 0 else slice(None) for i in range(data.ndim)))
    data = data[ind]
    
    if out is None:
        # now copy
        data = data.copy()
    else:
        assert out.dtype == data.dtype
        assert out.size == data.size
        assert out.ndim == 1
        out[:] = data.reshape(data.size)
        data = out
    # unreverse axes
    data = data[ind]
    # and untranspose
    data = data.transpose(np.argsort(order))
    return data


def is_contiguous(data):
    """Return True if *data* occupies a contiguous block of memory.
    
    Note this is _not_ the same as asking whether an array is C-contiguous
    or F-contiguous because it does not care about the axis order or 
    direction.
    """
    order = np.argsort(np.abs(data.strides))[::-1]
    strides = np.array(data.strides)[order]
    shape = np.array(data.shape)[order]
    
    if abs(strides[-1]) != data.itemsize:
        return False
    for i in range(data.ndim-1):
        if abs(strides[i]) != abs(strides[i+1] * shape[i+1]):
            return False
        
    return True


def decompose_array(data):
    """Return the components needed to efficiently serialize and unserialize
    an array:
    
    1. A contiguous data buffer that can be sent via socket
    2. An offset into the buffer
    3. Strides into the buffer
    
    Shape and dtype can be pulled directly from the array. 
    
    If the input array is discontiguous, it will be copied using axis_order_copy().
    """
    if not is_contiguous(data):
        # socket.send requires a contiguous buffer
        data = axis_order_copy(data)
        
    buf = normalized_array(data)
    offset = data.__array_interface__['data'][0] - buf.__array_interface__['data'][0]
    
    return buf, offset, data.strides


def normalized_array(data):
    """Return *data* with axis order and direction normalized.
    
    This will only transpose and reverse axes; the array data is not copied.
    If *data* is contiguous in memory, then this returns a C-contiguous array.
    """
    order = np.argsort(np.abs(data.strides))[::-1]    
    data = data.transpose(order)
    # reverse axes if needed
    ind = tuple((slice(None, None, -1) if data.strides[i] < 0 else slice(None) for i in range(data.ndim)))
    return data[ind]


