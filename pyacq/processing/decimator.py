# -*- coding: utf-8 -*-
"""

"""


import multiprocessing as mp
import numpy as np
import msgpack

import threading

import zmq

import time

import scipy.signal

from .base import ProcessingBase


class SimpleDecimator(ProcessingBase):
    def __init__(self, stream, streamhandler,
                            autostart = True,
                            downsampling_factor = 10,
                            
                            
                            ):
        ProcessingBase.__init__(self, stream, streamhandler =streamhandler)
        assert type(downsampling_factor) is int
        
        q = self.downsampling_factor = downsampling_factor
        
        if type(stream).__name__ == 'AnalogSignalSharedMemStream':
            self.out_stream = self.streamhandler.new_AnalogSignalSharedMemStream(name = self.stream.name+'decimated',
                                                            sampling_rate = self.stream.sampling_rate/q,
                                                            nb_channel = self.stream.nb_channel,
                                                            buffer_length = self.stream.buffer_length,
                                                            packet_size = self.stream.packet_size, 
                                                            dtype = self.stream.shared_array.dtype,
                                                            channel_names = self.stream.channel_names,
                                                            channel_indexes = self.stream.channel_indexes,            
                                                            )

        elif type(stream).__name__ == 'DigitalSignalSharedMemStream':
            self.out_stream = self.streamhandler.new_DigitalSignalSharedMemStream(name = self.stream.name+'decimated',
                                                            sampling_rate = self.stream.sampling_rate/q,
                                                            nb_channel = self.stream.nb_channel,
                                                            buffer_length = self.stream.buffer_length,
                                                            packet_size = self.stream.packet_size, 
                                                            channel_names = self.stream.channel_names,
                                                            )

        self.out_array = self.out_stream['shared_array'].to_numpy_array()
        self.half_size2 = self.out_array.shape[1]/2
            
        
        if autostart:
            self.start()
    
    def loop(self):
        port = self.stream['port']
        socket = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(port))
        
        out_socket = self.context.socket(zmq.PUB)
        out_socket.bind("tcp://*:{}".format(self.out_stream['port']))
        
        q = self.downsampling_factor
        
        self.last_pos = None
        while self.running:
            events = socket.poll(50)
            if events ==0:
                time.sleep(.05)
                continue
            
            message = socket.recv()
            pos = msgpack.loads(message)
            if self.last_pos is None:
                self.last_pos = pos - pos%q

            if q>1:
                pos = pos - pos%q
            
            new = pos - self.last_pos
            if new//q==0: continue
            head = pos%self.half_size+self.half_size
            tail = head - new
            
            out = self.in_array[:,tail:head:q]
            
            head2 = (pos//q)%self.half_size2
            tail2 = (self.last_pos//q)%self.half_size2
            if tail2<head2:
                self.out_array[:,tail2:head2]= out
                self.out_array[:,tail2+self.half_size2:head2+self.half_size2] = out
            else:
                self.out_array[:,head2+self.half_size2-new//q:head2+self.half_size2] = out
                if tail2!=0:
                    self.out_array[:,-(self.half_size2-tail2):] = out[:, :(self.half_size2-tail2)]
                if head2!=0:
                    self.out_array[:,:head2] = out[:, -head2:]
            
            out_socket.send(msgpack.dumps(pos//q))
            self.last_pos = pos
            
