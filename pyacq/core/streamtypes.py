# -*- coding: utf-8 -*-
"""
Intro
-----

This module type of different streams.
In short a stream is something regulary or irregulary sampled : video, signal channels, digital
channels, events, ...

All stream use zmq socket to distribute new sample (or chunk of sample or image or chink of image).
Some stream use plain data socket (compress or not). Some other stream use a share mem
array view through numpy for convinience and only send the index of the new sample, this macanism 
avoid mem copy.

A stream can be synchronous or asynchronous depending of the source (aka driver of device).
If a device is real time them the packet sended in zmq are also "real time" as zmq is fast enough.


Stream list:
------

  * AnalogSignalSharedMemStream
  * AnalogSignalPlainDataStream
  * DigitalSignalSharedMemStream


"""


import numpy as np

from .tools import SharedArray




class Stream(object):
    
    #for convinience must desapear
    def __getitem__(self, k):
        return self._params[k]
    
    def __getattr__(self, k):
        if k in self._params:
            return self._params[k]
        else:
            return object.__getattribute__(self, name)
    def __getstate__(self):
        return self._params
    def __setstate__(self, kargs):
        self._params     = {}
        self._params.update(kargs)

    

class AnalogSignalSharedMemStream(Stream):
    """
    This is a stream for multi analog channel device at fixed sampling rate.
    It use a a shared memory view via a numpy array.
    The absolut sample index position is send via  a zmq.PUB socket.
    This stream is uselfull for a multi-processing design on the same machine.
    
    The numpy array is 2 dim: 0=channel 1=sample.
    Sample are written in an circular way.
    For convinience, the array is written twice, stacked in time dimension.
    So the shape is nb_channel X (nb_sample*2).
    Each channel is continous in memory for better perf.
    
    So you can acces a chunk of data without np.concatenatie due to side
    effect(because circular) with that kind of code::
        
        #arr is the shared array
        # pos is the absolut
        nb_channel, half_size = arr.shape
        head = pos%half_size+half_size
        latest_100_pt = arr[chan, pos-100:pos]
    
    
    """
    def __init__(self, name = '', sampling_rate = 100.,
                                        nb_channel = 2, buffer_length = 8.192,
                                        packet_size = None, dtype = np.float32,
                                        channel_names = None, channel_indexes = None,
                                        port = None,
                                                    ):

        if channel_indexes is None:
            channel_indexes = range(nb_channel)
        if channel_names is None:
            channel_names = [ 'Channel {}'.format(i) for i in channel_indexes]
        
        s = self._params = { }
        s['name'] = name
        #~ s['type'] = 'signals_stream_sharedmem'
        s['sampling_rate'] = sampling_rate
        s['nb_channel'] = nb_channel
        s['packet_size'] = packet_size
        s['buffer_length'] = buffer_length
        s['channel_names'] = channel_names
        s['channel_indexes'] = channel_indexes
        
        l = int(sampling_rate*buffer_length)
        if packet_size is not None:
            assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        shape = (nb_channel, l*2)
        
        s['shared_array'] = SharedArray(shape = shape, dtype = np.dtype(dtype))
        s['port'] = port
        


class DigitalSignalSharedMemStream(Stream):
    """
    This is a stream for multi digital channel device at fixed sampling rate.
    It use a a shared memory view via a numpy array.
    The absolut sample index position is send via  a zmq.PUB socket.
    
    This stream is uselfull for a multi-processing design.
    
    Digital channel are grouped 8 by 8 in uint8. (a 8 bit port)
    
    The numpy array is 2 dim: 0=bytes 1=sample.
    Sample are written in an circular way.
    For convinience, the array is written twice, stacked in time dimension.
    So the shape is (nb_channel/8) X (nb_sample*2).
    
    See AnalogSignalSharedMemStream for accesing circular way.
    
    """
    def __init__(self, name = '', sampling_rate = 100.,
                                        nb_channel = 24, buffer_length = 8.192,
                                        packet_size = None, channel_names = None,
                                         port = None,
                                                    ):
        
        if channel_names is None:
            channel_names = [ 'Channel {}'.format(i) for i in range(nb_channel)]
        
        s = self._params = { }
        s['name'] = name
        #~ s['type'] = 'digital_stream_sharedmem'
        s['sampling_rate'] = sampling_rate
        s['nb_channel'] = nb_channel
        s['packet_size'] = packet_size
        s['buffer_length'] = buffer_length
        s['channel_names'] = channel_names
        
        l = int(sampling_rate*buffer_length)
        if packet_size is not None:
            assert l%packet_size ==0, 'buffer should be a multilple of packet_size {} {}'.format(l, packet_size)
        
        n_bytes = int(np.ceil(nb_channel/8.))
        
        shape = (n_bytes, l*2)
        s['shared_array'] = SharedArray(shape = shape, dtype = np.uint8)
        s['port'] = port


class AnalogSignalPlainDataStream(Stream):
    """
    This is a stream for multi analog channel device at fixed sampling rate.
    It is similar to AnalogSignalSharedMemStream but do not have shared mem.
    All samples are sended via a socket and compressed  or not via blosc, lz4 or snappy.
    
    This stream is uselfull for design with several station becaus eno sharedmem.
    
    
    """
    def __init__(self, name = '', sampling_rate = 100.,  nb_channel = 2,
                                        packet_size = None, dtype = np.float32,
                                        channel_names = None, channel_indexes = None,
                                        compress = 'blosc', port = None, 
                                                    ):
        
        if channel_names is None:
            channel_names = [ 'Channel {}'.format(i) for i in range(nb_channel)]
        
        s = self._params = { }
        s['name'] = name
        s['sampling_rate'] = sampling_rate
        s['nb_channel'] = nb_channel
        s['nb_channel'] = nb_channel
        s['packet_size'] = packet_size
        s['dtype'] = dtype
        s['channel_names'] = channel_names
        s['channel_indexes'] = channel_indexes
        s['compress'] = compress
        
        
        s['port'] = port


stream_type_list = [AnalogSignalSharedMemStream, DigitalSignalSharedMemStream, AnalogSignalPlainDataStream ]


