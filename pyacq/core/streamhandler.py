# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack

from collections import OrderedDict
from .tools import SharedArray
from .streamtypes import stream_type_list

"""




"""


class StreamHandler:
    """
    
    
    
    """
    def __init__(self):
        self.streams = OrderedDict()
        
        ## small hock for generating self.new_AnalogSignalSharedMemStream
        class caller:
            def __init__(self, inst, streamclass):
                self.inst = inst
                self.streamclass = streamclass
            def __call__(self,  **kargs):
                #~ print self, self.inst, self.streamclass, kargs
                return self.inst.get_new_stream(  self.streamclass, **kargs)
        for stream_type in stream_type_list:
            setattr(self, 'new_'+stream_type.__name__, caller(self, stream_type))
        ##
    
    def new_port(self, addr = 'tcp://*'):
        import zmq
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        available_port = socket.bind_to_random_port(addr, min_port=5000, max_port=10000, max_tries=100)
        socket.close()
        return available_port
    
    def get_new_stream(self, streamclass, port = None, **kargs):
        if port is None:
            port = self.new_port()
        stream = streamclass(port = port, **kargs)
        self.streams[port] = stream
        return stream
