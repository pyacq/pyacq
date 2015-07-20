import zmq


default_stream = dict( protocol = 'tcp', bind_addr = '127.0.0.1', port = '8000',
                        transfertmode = 'plaindata', streamtype = 'analogsignal',
                        dtype = 'float32', shape = (-1, 16), compression ='',
                        scale = None, offset = None, units = '')


common_doc = """
    Parameters
    ----------
    protocol : 'tcp', 'udp', 'inproc' or 'inpc' (linux only)
        The type of protocol user for the zmq.PUB socket
    addr : str
        The bind adress for the zmq.PUB socket
    port : str
        The port for the zmq.PUB socket
    transfertmode: 'plain_data', 'shared_mem', (not done 'shared_cuda_buffer' or 'share_opencl_buffer')
        The way how the data transfet is done:
            * 'plain_data' :  the data is send in the socket with a two part : one for frame index one for data.
            * 'shared_mem' : the data is share in memory in a ring buffer, the socket only send the frame index
            * 'shared_cuda_buffer' the data is share in Cuda buffer, the socket only send the frame index
            * 'share_opencl_buffer' the data is share in OpenCL buffer, the socket only send the frame index
    streamtype: 'analogsignal', 'digitalsignal', 'event' or 'image/video'
        The type of data that are transfert.
    dtype: str ('float32','float64', [('r', 'uint16'), ('g', 'uint16'), , ('b', 'uint16')], ...)
        The numpy.dtype of the data buffer. It can be a composed dtype for event or images.
    shape: list
        The shape of each data frame. Unknown dim are -1 in case of variable chunk.
            * for image it is HxW.
            * for analogsignal it can (nb_sample x nb_channel) or (-1 x nb_channel)
    compression: '', 'blosc', 'blosc-lz4', 'mp4', 'h264'
        The compression for the data stream, the default is no compression ''.
    scale: float
        In case when dtype is integer, you can give optional scale and offset. 
        real_data = offset + scale*data
    offset:
        See scale.
    units: str
        Units of the stream. mainly used for 'analogsignal'
"""

class StreamDef:
    """
    A StreamDef define a connection between 2 nodes.
    
    """+common_doc
    def __init__(self,**karg):
        self.params = dict(default_stream)
        self.params.update(kargs)
    

class StreamSender:
    """
    A StreamSender is a helper class to send data.
    
    
    """
    def __init__(self, **kargs):
        self.params = dict(default_stream)
        self.params.update(kargs)
        
        url = '{protocol}://{addr}:{port}'.format(**self.params)
        
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(url)
        
        if compression != '':
            assert self.params['transfertmode'] == 'plaindata', 'Compression only for transfertmode=plaindata'
        
        self.funcs = []
        if self.params['transfertmode'] == 'plaindata':
            pass
        elif self.params['transfertmode'] == 'shared_mem':
            pass
        
        #elif self.params['transfertmode'] == 'shared_cuda_buffer':
        #    pass
        #elif self.params['transfertmode'] == 'share_opencl_buffer':
        #   pass

        
    
    def send(self, index, data):
        """
        
        """
        for f in self.funcs:
            data = f(data)


    #~ def _send_plaindata(self):
        
    




class StreamReceiver:
    """
    A StreamSender is a helper class to receiv data.
    
    """
    def __init__(self, **kargs):
        self.params = dict(default_stream)
        self.params.update(kargs)


