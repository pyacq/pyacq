# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack

from collections import OrderedDict
from .tools import SharedArray


class StreamHandler:
    """
    
    
    """
    def __init__(self, stream_port = 5555):
        self.stream_port = stream_port
        self.streams = OrderedDict()
    
    def new_port(self):
        # FIXME : test if available
        self.stream_port += 1
        return self.stream_port
    
    def new_signals_stream(self, name = '', sampling_rate = 100.,
                                        nb_channel = 2, buffer_length = 8.192,
                                        packet_size = 64, dtype = np.float32,
                                        channel_names = None, channel_indexes = None,            
                                                    ):
        
        s = stream = { }
        s['name'] = name
        s['type'] = 'signals_stream'
        s['sampling_rate'] = sampling_rate
        s['nb_channel'] = nb_channel
        s['packet_size'] = packet_size
        s['buffer_length'] = buffer_length
        s['channel_names'] = channel_names
        s['channel_indexes'] = channel_indexes
        
        l = int(sampling_rate*buffer_length)
        assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        shape = (nb_channel, l)
        
        s['shared_array'] = SharedArray(shape = shape, dtype = np.dtype(dtype))
        s['port'] = self.new_port()
        self.streams[s['port']] = stream
        
        return stream