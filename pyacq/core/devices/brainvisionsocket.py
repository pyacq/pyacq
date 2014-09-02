# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack
import time
from collections import OrderedDict

import struct
import socket

from .base import DeviceBase

class Marker:
    def __init__(self):
        self.position = 0
        self.points = 0
        self.channel = -1
        self.type = ""
        self.description = ""

dtype_trigger = [('pos', 'int64'),
                            ('points', 'int64'),
                            ('channel', 'int64'),
                            ('type', 'S16'),#TODO check size
                            ('description', 'S16'),#TODO check size
                            ]

def recv_data(brain_socket, requestedSize):
    buf = np.empty( requestedSize, dtype = np.uint8)
    n = 0
    while n < requestedSize:
        databytes = brain_socket.recv(requestedSize - n)
        if databytes == '':
            raise RuntimeError, "connection broken"
        buf[n:n+len(databytes)] = np.frombuffer(databytes, dtype = np.uint8)
        n += len(databytes)
    return buf

def get_signal_and_markers(rawdata, nb_channel):
    
    hs = 12
    dt = np.dtype(np.float32)
    
    # Extract numerical data
    (block, points, nb_marker) = struct.unpack('<LLL', rawdata[:hs])
    n = nb_channel
    sigs = (rawdata[hs:hs+points*n*dt.itemsize]).view(dt)
    sigs = sigs.reshape(points, n)

    # Extract markers
    markers = np.empty((nb_marker,), dtype = dtype_trigger)
    index = 12 + 4 * points * n
    for m in range(nb_marker):
        markersize, = struct.unpack('<L', rawdata[index:index+4])
        markers['pos'][m], markers['points'][m],markers['channel'][m] = struct.unpack('<LLl', rawdata[index+4:index+16])
        markers['type'][m], markers['description'][m] = rawdata[index+16:index+markersize].split('\x00')[:2]
        index = index + markersize

    return block, sigs, markers
    
def brainvisionsocket_mainLoop(stop_flag, streams, brain_host, brain_port, resolutions):
    import zmq
    abs_pos = pos2 = 0
    
    context = zmq.Context()
    
    stream0 = streams[0]
    socket0 = context.socket(zmq.PUB)
    socket0.bind("tcp://*:{}".format(stream0['port']))
    socket0.send(msgpack.dumps(abs_pos))
    
    stream1 = streams[1]
    socket1 = context.socket(zmq.PUB)
    socket1.bind("tcp://*:{}".format(stream1['port']))
    
    brain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    brain_socket.connect((brain_host, brain_port))
    
    packet_size = stream0['packet_size']
    sampling_rate = stream0['sampling_rate']
    np_arr = stream0['shared_array'].to_numpy_array()
    half_size = np_arr.shape[1]/2
    while True:
        buf_header = recv_data(brain_socket, 24)
        (id1, id2, id3, id4, msgsize, msgtype) = struct.unpack('<llllLL', buf_header)
        rawdata = recv_data(brain_socket,  msgsize - 24)
        if msgtype == 1:
            pass
        elif msgtype == 4:
            block, chunk, markers = get_signal_and_markers(rawdata, stream0.nb_channel)
            
            # Signals
            chunk *= resolutions[np.newaxis, :]
            packet_size = chunk.shape[0]
            np_arr[:,pos2:pos2+packet_size] = chunk.transpose() 
            np_arr[:,pos2+half_size:pos2+packet_size+half_size] = chunk.transpose()
            if pos2+packet_size>half_size:
                pass
                #TODO : check packet_size
            abs_pos += packet_size
            pos2 = abs_pos%half_size
            socket0.send(msgpack.dumps(abs_pos))
            
            #Triggers
            for marker in markers:
                socket1.send(marker.tostring())
            

        elif msgtype == 3:
            break
    
    brain_socket.close()
    


def create_analog_subdevice_param(n):
    d = {
                'type' : 'AnalogInput',
                'nb_channel' : n,
                'params' :{  }, 
                'by_channel_params' : { 
                                        'channel_indexes' : range(n),
                                        'channel_names' : [ 'AI Channel {}'.format(i) for i in range(n)],
                                        'channel_selection' : [True]*n,
                                        }
            }
    return d
    
class BrainvisionSocket(DeviceBase):
    """
    Usage:
        dev = FakeMultiSignals()
        dev.configure(...)
        dev.initialize()
        dev.start()
        dev.stop()
        
    Configuration Parameters:
        nb_channel
        sampling_rate
        buffer_length
        packet_size
        channel_names
        channel_indexes
    
    
    """
    def __init__(self,  **kargs):
        DeviceBase.__init__(self, **kargs)
    
    def configure(self, 
                        buffer_length= 10.,
                        brain_host = 'localhost',
                        brain_port = 51244,                        
                        #~ subdevices =[ ],
                        ):
        

        #~ subdevices = [ ]
        self.params = {
                                'buffer_length' : buffer_length,
                                'brain_host' : brain_host,
                                'brain_port' : brain_port,
                                
                                }
        self.__dict__.update(self.params)
        self.configured = True

    @classmethod
    def get_available_devices(cls):
        devices = OrderedDict()
        return devices
        

    def initialize(self, streamhandler = None):
        brain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        brain_socket.connect((self.brain_host, self.brain_port))
        
        buf_header = recv_data(brain_socket, 24)
        (id1, id2, id3, id4, msgsize, msgtype) = struct.unpack('<llllLL', buf_header)
        rawdata = recv_data(brain_socket,  msgsize - 24)
        if msgtype == 1:
            nb_channel, sampling_interval = struct.unpack('<Ld', rawdata[:12])
            n = nb_channel
            sampling_interval *= 1e-6
            sampling_rate = 1./sampling_interval
            self.resolutions = np.array(struct.unpack('<'+'d'*n, rawdata[12:12+8*n]), dtype = 'f')
            channel_names = rawdata[12+8*n:].tostring().split('\x00')[:-1]
            channel_indexes = range(nb_channel)
        else:
            print 'error'
        
        brain_socket.close()
        
        

        #sub0 = self.subdevices[0]
        #sel = sub0['by_channel_params']['channel_selection']
        packet_size = int(20e-3*sampling_rate)
        l = int(sampling_rate*self.buffer_length)
        self.buffer_length = (l - l%packet_size)/sampling_rate
        
        name = 'Brainvision socket {}'.format(nb_channel)
        #FIXME : name
        s0 = self.streamhandler.new_AnalogSignalSharedMemStream(name = name, sampling_rate = sampling_rate,
                                                        nb_channel = nb_channel, buffer_length = self.buffer_length,
                                                        packet_size = packet_size, dtype = np.float64,
                                                        channel_names = channel_names, channel_indexes = channel_indexes,            
                                                        )
        
        s1 = self.streamhandler.new_AsynchronusEventStream(name = 'Brainvision socket triggers', 
                        dtype =  dtype_trigger)
        
        
        self.streams = [s0, s1]
        
        #~ arr_size = s['shared_array'].shape[1]
        #~ assert (arr_size/2)%self.packet_size ==0, 'buffer should be a multilple of pcket_size {}/2 {}'.format(arr_size, self.packet_size)

        print 'BrainvisionSocket initialized analog:',  s0['port']
        print 'BrainvisionSocket initialized trigger:',  s1['port']
    
    def start(self):
        self.stop_flag = mp.Value('i', 0) #flag pultiproc
        self.process = mp.Process(target = brainvisionsocket_mainLoop,  args=(self.stop_flag, self.streams, self.brain_host, self.brain_port, self.resolutions) )
        self.process.start()
        
        print 'BrainvisionSocket started:'
        self.running = True
    
    def stop(self):
        self.stop_flag.value = 1
        self.process.join()
        print 'BrainvisionSocket stopped:'
        
        self.running = False
    
    def close(self):
        pass
