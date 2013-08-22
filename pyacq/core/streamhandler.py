# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack

from collections import OrderedDict
from .tools import SharedArray

"""




"""

#~ class Stream:
    #~ pass


#~ class AnalogSignalSharedMemStream(Stream):
    #~ """
    #~ This is a stream for multi analog channel device at fixed sampling rate.
    #~ It use a a shared memory view via a numpy array.
    #~ The absolut sample index position is send via  a zmq.PUB socket.
    #~ This stream is uselfull for a multi-processing design on the same machine.
    
    #~ The numpy array is 2 dim: 0=channel 1=sample.
    #~ Sample are written in an circular way.
    #~ For convinience, the array is written twice, stacked in time dimension.
    #~ So the shape is nb_channel X (nb_sample*2).
    #~ Each channel is continous in memory for better perf.
    
    #~ So you can acces a chunk of data without np.concatenatie due to side
    #~ effect(because circular) with that kind of code::
        
        #~ #arr is the shared array
        #~ # pos is the absolut
        #~ nb_channel, half_size = arr.shape
        #~ head = pos%half_size+half_size
        #~ latest_100_pt = arr[chan, pos-100:pos]
    
    
    #~ """
    #~ def __init__(self, name = '', sampling_rate = 100.,
                                        #~ nb_channel = 2, buffer_length = 8.192,
                                        #~ packet_size = 64, dtype = np.float32,
                                        #~ channel_names = None, channel_indexes = None,            
                                                    #~ ):

        #~ if channel_indexes is None:
            #~ channel_indexes = range(nb_channel)
        #~ if channel_names is None:
            #~ channel_names = [ 'Channel {}'.format(i) for i in channel_indexes]
        
        #~ s = stream = { }
        #~ s['name'] = name
        #~ s['type'] = 'signals_stream_sharedmem'
        #~ s['sampling_rate'] = sampling_rate
        #~ s['nb_channel'] = nb_channel
        #~ s['packet_size'] = packet_size
        #~ s['buffer_length'] = buffer_length
        #~ s['channel_names'] = channel_names
        #~ s['channel_indexes'] = channel_indexes
        
        #~ l = int(sampling_rate*buffer_length)
        #~ assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        #~ shape = (nb_channel, l*2)
        
        #~ s['shared_array'] = SharedArray(shape = shape, dtype = np.dtype(dtype))
        #~ s['port'] = self.new_port()
        #~ self.streams[s['port']] = stream


#~ class DigitalSignalSharedMemStream(Stream):
    #~ """
    #~ This is a stream for multi digital channel device at fixed sampling rate.
    #~ It use a a shared memory view via a numpy array.
    #~ The absolut sample index position is send via  a zmq.PUB socket.
    
    #~ This stream is uselfull for a multi-processing design.
    
    #~ Digital channel are grouped 8 by 8 in uint8. (a 8 bit port)
    
    #~ The numpy array is 2 dim: 0=bytes 1=sample.
    #~ Sample are written in an circular way.
    #~ For convinience, the array is written twice, stacked in time dimension.
    #~ So the shape is (nb_channel/8) X (nb_sample*2).
    
    #~ See AnalogSignalSharedMemStream for accesing circular way.
    
    #~ """
    #~ def __init__(self, name = '', sampling_rate = 100.,
                                        #~ nb_channel = 24, buffer_length = 8.192,
                                        #~ packet_size = 64, channel_names = None,
                                         
                                                    #~ ):
        #~ """
        #~ Shared mem doucle buffer size
        #~ """
        #~ if channel_names is None:
            #~ channel_names = [ 'Channel {}'.format(i) for i in range(nb_channel)]
        
        #~ s = stream = { }
        #~ s['name'] = name
        #~ s['type'] = 'digital_stream_sharedmem'
        #~ s['sampling_rate'] = sampling_rate
        #~ s['nb_channel'] = nb_channel
        #~ s['packet_size'] = packet_size
        #~ s['buffer_length'] = buffer_length
        #~ s['channel_names'] = channel_names
        
        #~ l = int(sampling_rate*buffer_length)
        #~ assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        
        #~ n_bytes = int(np.ceil(nb_channel/8.))
        
        #~ shape = (n_bytes, l*2)
        #~ s['shared_array'] = SharedArray(shape = shape, dtype = np.uint8)
        #~ s['port'] = self.new_port()
        #~ self.streams[s['port']] = stream
        
        #~ return stream

#~ class AnalogSignalStream(Stream):
    #~ """
    #~ This is a stream for multi analog channel device at fixed sampling rate.
    #~ It is similar to AnalogSignalSharedMemStream but do not have shared mem.
    #~ All samples are sended via a socket and compressed via blosc, lz4 or snappy.
    
    #~ This stream offer 2 sockets:
        #~ 1 - a zmq.REP (server) with fixed port for getting parameters.
        #~ 2 - a zmq.PUB for sending absolut sample position and array chunk on a generated port.
    
    #~ This stream is uselfull for design with several station.
    
    
    #~ """
    #~ def __init__(self, name = '', sampling_rate = 100.,
                                        #~ nb_channel = 2, buffer_length = 8.192,
                                        #~ packet_size = 64, dtype = np.float32,
                                        #~ channel_names = None, channel_indexes = None,            
                                                    #~ ):


class StreamHandler:
    """
    
    
    
    """
    def __init__(self):
        self.streams = OrderedDict()
    
    def new_port(self, addr = 'tcp://*'):
        import zmq
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        available_port = socket.bind_to_random_port(addr, min_port=5000, max_port=10000, max_tries=100)
        socket.close()
        return available_port
    
    def new_signals_stream(self, name = '', sampling_rate = 100.,
                                        nb_channel = 2, buffer_length = 8.192,
                                        packet_size = 64, dtype = np.float32,
                                        channel_names = None, channel_indexes = None,            
                                                    ):
        """
        Shared mem doucle buffer size
        """
        if channel_indexes is None:
            channel_indexes = range(nb_channel)
        if channel_names is None:
            channel_names = [ 'Channel {}'.format(i) for i in channel_indexes]
        
        s = stream = { }
        s['name'] = name
        s['type'] = 'signals_stream_sharedmem'
        s['sampling_rate'] = sampling_rate
        s['nb_channel'] = nb_channel
        s['packet_size'] = packet_size
        s['buffer_length'] = buffer_length
        s['channel_names'] = channel_names
        s['channel_indexes'] = channel_indexes
        
        l = int(sampling_rate*buffer_length)
        assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        shape = (nb_channel, l*2)
        
        s['shared_array'] = SharedArray(shape = shape, dtype = np.dtype(dtype))
        s['port'] = self.new_port()
        self.streams[s['port']] = stream
        
        return stream

    def new_digital_stream(self, name = '', sampling_rate = 100.,
                                        nb_channel = 24, buffer_length = 8.192,
                                        packet_size = 64, channel_names = None,
                                         
                                                    ):
        """
        Shared mem doucle buffer size
        """
        if channel_names is None:
            channel_names = [ 'Channel {}'.format(i) for i in range(nb_channel)]
        
        s = stream = { }
        s['name'] = name
        s['type'] = 'digital_stream_sharedmem'
        s['sampling_rate'] = sampling_rate
        s['nb_channel'] = nb_channel
        s['packet_size'] = packet_size
        s['buffer_length'] = buffer_length
        s['channel_names'] = channel_names
        
        l = int(sampling_rate*buffer_length)
        assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        
        n_bytes = int(np.ceil(nb_channel/8.))
        
        shape = (n_bytes, l*2)
        s['shared_array'] = SharedArray(shape = shape, dtype = np.uint8)
        s['port'] = self.new_port()
        self.streams[s['port']] = stream
        
        return stream

