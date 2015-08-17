import zmq
import numpy as np
try:
    import blosc
    HAVE_BLOSC = True
except ImportError:
    HAVE_BLOSC = False

from .sharedarray import SharedArray

default_stream = dict( protocol = 'tcp', interface = '127.0.0.1', port = '8000',
                        transfermode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), time_axis = 0, 
                        compression ='', scale = None, offset = None, units = '')


common_doc = """
    Parameters
    ----------
    protocol : 'tcp', 'udp', 'inproc' or 'inpc' (linux only)
        The type of protocol user for the zmq.PUB socket
    interface : str
        The bind adress for the zmq.PUB socket
    port : str
        The port for the zmq.PUB socket
    transfermode: 'plain_data', 'shared_array', (not done 'shared_cuda_buffer' or 'share_opencl_buffer')
        The method used for data transfer:
            * 'plain_data': data are sent over a plain socket in two parts: (frame index, data).
            * 'shared_array': data are stored in shared memory in a ring buffer and the current frame index is sent over the socket.
            * 'shared_cuda_buffer': data are stored in shared Cuda buffer and the current frame index is sent over the socket.
            * 'share_opencl_buffer': data are stored in shared OpenCL buffer and the current frame index is sent over the socket.
    streamtype: 'analogsignal', 'digitalsignal', 'event' or 'image/video'
        The type of data to be transferred.
    dtype: str ('float32','float64', [('r', 'uint16'), ('g', 'uint16'), , ('b', 'uint16')], ...)
        The numpy.dtype of the data buffer. It can be a composed dtype for event or images.
    shape: list
        The shape of each data frame. Unknown dim are -1 in case of variable chunk.
            * for image it is (-1, H, W), (n_frames, H, W), or (H, W).
            * for analogsignal it can be (n_samples, n_channels) or (-1, n_channels)
    time_axis: int
        The index of the axis that represents time within a single data chunk, or
        -1 if the chunk lacks this axis (in this case, each chunk represents exactly one
        timepoint).
    compression: '', 'blosclz', 'blosc-lz4', 'mp4', 'h264'
        The compression for the data stream, the default is no compression ''.
    scale: float
        An optional scale factor + offset to apply to the data before it is sent over the stream.
        real_data = offset + scale * data
    offset:
        See scale.
    units: str
        Units of the stream. Mainly used for 'analogsignal'.
    sampling_rate: float or None
        Sampling rate of the stream in Hz.
    sampling_interval: float or None
        
    
    Parameters when using `transfermode` = 'shared_array'
    -----
    shared_array_shape: tuple
        Shape of the SharedArray
    ring_buffer_method: 'double' or 'single'
        Method for the ring buffer:
            *  'double' : there 2 ring buffer concatenated. This ensure continuous chunk whenever the sample position.
            * 'single': standart ring buffer
        Note that, The ring buffer is along `time_axis` for each case. And in case, of 'double', concatenated axis is also `time_axis`.
    shm_id : str or int (depending on platform)
        id of the SharedArray
        
    
    
"""

class StreamDef(dict):
    """StreamDef defines a connection between 2 nodes.
    """+common_doc
    
    

class StreamSender:
    """A StreamSender is a helper class to send data.
    """
    def __init__(self, **kargs):
        self.params = dict(default_stream)
        self.params.update(kargs)
        
        self.url = '{protocol}://{interface}:{port}'.format(**self.params)
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(self.url)
        self.addr = self.socket.getsockopt(zmq.LAST_ENDPOINT).decode()
        self.port = self.addr.rpartition(':')[2]
        self.params['port'] = self.port
        
        self.funcs = []
        
        if self.params['compression'] != '':
            assert self.params['transfermode'] == 'plaindata', 'Compression only for transfermode=plaindata'
        
        #compression
        if self.params['compression'] == '':
            pass
        elif self.params['compression'] == 'blosc-blosclz':
            #cname for ['blosclz', 'lz4', 'lz4hc', 'snappy', 'zlib']
            self.funcs.append(self._compress_blosclz)
        elif self.params['compression'] == 'blosc-lz4':
            self.funcs.append(self._compress_blosclz4)
            
        
        #send or cpy to buffer
        if self.params['transfermode'] == 'plaindata':
            self.funcs.append(self._send_plain)
        
        elif self.params['transfermode'] == 'shared_array':
            if self.params['ring_buffer_method'] == 'single':
                self.funcs.append(self._copy_to_sharray_single)
            elif self.params['ring_buffer_method'] == 'double':
                self.funcs.append(self._copy_to_sharray_double)
            
            self._index = 0
            
            # prepare SharedArray
            self._time_axis = self.params['time_axis']
            self._ring_size = self.params['shared_array_shape'][self._time_axis]
            shared_array_shape = list(self.params['shared_array_shape'])
            self._ndim = len(shared_array_shape)
            assert self._ndim==len(self.params['shape']), 'shared_array_shape and shape must coherent!'
            if self.params['ring_buffer_method'] == 'double':
                shared_array_shape[self._time_axis] = self._ring_size*2
            self._sharedarray = SharedArray(shape = shared_array_shape, dtype = self.params['dtype'])
            self.params['shm_id'] = self._sharedarray.shm_id
            self._numpyarr = self._sharedarray.to_numpy()
            
            
        #elif self.params['transfermode'] == 'shared_cuda_buffer':
        #    pass
        #elif self.params['transfermode'] == 'share_opencl_buffer':
        #   pass
        
        #TODO check if this is needed
        self.copy = self.params['protocol'] == 'inproc'

    def send(self, index, data):
        """
        Send the data chunk and its frame index.
        
        Parameters
        ----------
        index: int
            The absolut sample index. If the chunk is multiple sample then index is the last one (head).
        data: np.ndarray or bytes
            The chunk of data to be send
        """
        for f in self.funcs:
            index, data = f(index, data)
    
    def _send_plain(self, index, data):
        self.socket.send_multipart([np.int64(index), data], copy = self.copy)
        return None, None
    
    def _copy_to_sharray_single(self, index, data):
        assert data.shape[self._time_axis]<self._ring_size, 'The chunk is too big for the buffer {} {}'.format(data.shape, self._numpyarr.shape)
        head = index % self._ring_size
        tail =  self._index%self._ring_size
        if head>tail:
            # 1 chunks
            sl = [slice(None)] * self._ndim
            sl[self._time_axis] = slice(tail, head)
            self._numpyarr[sl] = data
        else:
            # 2 chunks : because end of the ring
            size1 = self._ring_size-tail
            size2 = data.shape[self._time_axis] - size1
            
            #part1
            sl1 = [slice(None)] * self._ndim 
            sl1[self._time_axis] = slice(tail, None)
            sl2 = [slice(None)] * self._ndim 
            sl2[self._time_axis] = slice(None, size1)
            self._numpyarr[sl1] = data[sl2]
            
            #part2
            sl3 = [slice(None)] * self._ndim
            sl3[self._time_axis] = slice(None, size2)
            sl4 = [slice(None)] * self._ndim
            sl4[self._time_axis] = slice(-size2, None)
            self._numpyarr[sl3] = data[sl4]
        
        self.socket.send(np.int64(index), copy = self.copy)
        self._index += data.shape[self._time_axis]
        return index, None

    def _copy_to_sharray_double(self, index, data):
        head = index % self._ring_size
        tail =  self._index%self._ring_size
        if head>tail:
            sl = [slice(None)] * self._ndim
            sl[self._time_axis] = slice(tail, head)
            # 1 chunk
            self._numpyarr[sl] = data
            # 1 same chunk
            sl[self._time_axis] = slice(tail+self._ring_size, head+self._ring_size)
            self._numpyarr[sl] = data
            
        else:
            size1 = self._ring_size-tail
            size2 = data.shape[self._time_axis] - size1
            
            # 1 full chunks continuous
            sl = [slice(None)] * self._ndim 
            sl[self._time_axis] = slice(tail, head+self._ring_size)
            self._numpyarr[sl] = data
            
            #part1 : in the second ring
            sl1 = [slice(None)] * self._ndim 
            sl1[self._time_axis] = slice(tail+self._ring_size, None)
            sl2 = [slice(None)] * self._ndim 
            sl2[self._time_axis] = slice(None, size1)
            self._numpyarr[sl1] = data[sl2]
            
            # part2 : in the first ring
            sl3 = [slice(None)] * self._ndim
            sl3[self._time_axis] = slice(None, size2)
            sl4 = [slice(None)] * self._ndim
            sl4[self._time_axis] = slice(-size2, None)
            self._numpyarr[sl3] = data[sl4]
            
        self.socket.send(np.int64(index), copy = self.copy)
        self._index += data.shape[self._time_axis]
        return index, None
    
    def _compress_blosclz(self, index, data):
        assert HAVE_BLOSC, "Cannot use blosclz compression; blosc package is not importable."
        data = blosc.pack_array(data, cname = 'blosclz')
        return index, data
    
    def _compress_blosclz4(self, index, data):
        assert HAVE_BLOSC, "Cannot use blosclz4 compression; blosc package is not importable."
        data = blosc.pack_array(data, cname = 'lz4')
        return index, data
    
    def close(self):
        self.socket.close()
        if self.params['transfermode'] == 'shared_array':
            self._sharedarray.close()


class StreamReceiver:
    """StreamSender is a helper class to receive data.
    """
    def __init__(self, **kargs):
        self.params = dict(default_stream)
        self.params.update(kargs)

        self.url = '{protocol}://{interface}:{port}'.format(**self.params)
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE,b'')
        self.socket.connect(self.url)
        
        self.funcs = []
        #send or cpy to buffer
        if self.params['transfermode'] == 'plaindata':
            self.funcs.append(self._recv_plain)
            #compression
            if self.params['compression'] == '':
                self.funcs.append(self._numpy_fromstring)
            elif self.params['compression'] in ['blosc-blosclz', 'blosc-lz4']:
                self.funcs.append(self._uncompress_blosc)
        elif self.params['transfermode'] == 'shared_array':
            self.funcs.append(self._recv_from_shmem)
            
            self._time_axis = self.params['time_axis']
            self._ring_size = self.params['shared_array_shape'][self._time_axis]
            shared_array_shape = list(self.params['shared_array_shape'])
            self._ndim = len(shared_array_shape)
            assert self._ndim==len(self.params['shape']), 'shared_array_shape and shape must coherent!'
            if self.params['ring_buffer_method'] == 'double':
                shared_array_shape[self._time_axis] = self._ring_size*2
            self._sharedarray = SharedArray(shape = shared_array_shape, dtype = self.params['dtype'], shm_id = self.params['shm_id'])
            self._numpyarr = self._sharedarray.to_numpy()
    
    def recv(self):
        """
        Receive the index and the data chunk.
        """
        index, data = self.funcs[0]()
        for f in self.funcs[1:]:
            index, data = f(index, data)
        return index, data
    
    def get_array_slice(self, index, length):
        """
        For shared_array transfert, you can a any chunk size (no more than the ring size)
        """
        assert self.params['transfermode'] == 'shared_array', 'For shared_array only'
        assert self.params['ring_buffer_method'] == 'double', 'For double ring buffer only'
        assert length<self._ring_size, 'The ring size is too small {} {}'.format(self._ring_size, length)
        i2 = index%self._ring_size + self._ring_size
        i1 = i2 - length
        sl = [slice(None)] * self._ndim 
        sl[self._time_axis] = slice(i1,i2)
        return self._numpyarr[sl]
    
    def _recv_plain(self):
        m0,m1 = self.socket.recv_multipart()
        index = np.fromstring(m0, dtype = 'int64')[0]
        return index, m1

    def _recv_from_shmem(self):
        m0 = self.socket.recv()
        index = np.fromstring(m0, dtype = 'int64')[0]
        return index, None
    
    def _numpy_fromstring(self, index, data):
        data  = np.frombuffer(data, dtype = self.params['dtype']).reshape(self.params['shape'])
        return index, data
    
    def _uncompress_blosc(self, index, data):
        data = blosc.unpack_array(data)
        return index, data
    
    def close(self):
        self.socket.close()
