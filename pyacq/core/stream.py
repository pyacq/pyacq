import zmq
import numpy as np
try:
    import blosc
    HAVE_BLOSC = True
except ImportError:
    HAVE_BLOSC = False


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
    transfermode: 'plain_data', 'shared_mem', (not done 'shared_cuda_buffer' or 'share_opencl_buffer')
        The method used for data transfer:
            * 'plain_data': data are sent over a plain socket in two parts: (frame index, data).
            * 'shared_mem': data are stored in shared memory in a ring buffer and the current frame index is sent over the socket.
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
        elif self.params['transfermode'] == 'shared_mem':
            self.funcs.append(self._copy_to_shmem)
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
    
    def _copy_to_shmem(self, index, data):
        raise(NotImplemented)
    
    def _compress_blosclz(self, index, data):
        assert HAVE_BLOSC, "Cannot use blosclz compression; blosc package is not importable."
        data = blosc.pack_array(data, cname = 'blosclz')
        return index, data
    
    def _compress_blosclz4(self, index, data):
        assert HAVE_BLOSC, "Cannot use blosclz4 compression; blosc package is not importable."
        data = blosc.pack_array(data, cname = 'lz4')
        return index, data
    
    def close(self):
        if self.params['protocol'] == 'tcp':
            self.socket.unbind(self.url)
        self.socket.close()


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
        elif self.params['transfermode'] == 'shared_mem':
            self.funcs.append(self._recv_from_shmem)
        
        #compression
        if self.params['compression'] == '':
            self.funcs.append(self._numpy_fromstring)
        elif self.params['compression'] in ['blosc-blosclz', 'blosc-lz4']:
            self.funcs.append(self._uncompress_blosc)

    def recv(self):
        """
        Receive the data chunk
        """
        index, data = self.funcs[0]()
        for f in self.funcs[1:]:
            index, data = f(index, data)
        return index, data
    
    def _recv_plain(self):
        m0,m1 = self.socket.recv_multipart()
        index = np.fromstring(m0, dtype = 'int64')[0]
        return index, m1

    def _recv_from_shmem(self):
        #~ m0 = self.socket.recv()
        #~ index = np.fromstring(m0, dtype = 'int64')[0]
        raise(NotImplemented)
    
    def _numpy_fromstring(self, index, data):
        data  = np.frombuffer(data, dtype = self.params['dtype']).reshape(self.params['shape'])
        return index, data
    
    def _uncompress_blosc(self, index, data):
        data = blosc.unpack_array(data)
        return index, data
    
    def close(self):
        self.socket.close()
