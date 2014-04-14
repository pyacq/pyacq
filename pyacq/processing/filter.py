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


class BandPassFilter(ProcessingBase):
    def __init__(self, stream, streamhandler,
                            autostart = True,
                            f_start = 0.,
                            f_stop = np.inf,
                            ):
        ProcessingBase.__init__(self, stream, streamhandler =streamhandler)
        
        self.out_stream = self.streamhandler.new_AnalogSignalSharedMemStream(name = self.stream.name+'filtered',
                                                        sampling_rate = self.stream.sampling_rate,
                                                        nb_channel = self.stream.nb_channel,
                                                        buffer_length = self.stream.buffer_length,
                                                        packet_size = self.stream.packet_size, 
                                                        dtype = self.stream.shared_array.dtype,
                                                        channel_names = self.stream.channel_names,
                                                        channel_indexes = self.stream.channel_indexes,            
                                                        )

        self.out_array = self.out_stream['shared_array'].to_numpy_array()
        
        self.f_start, self.f_stop = f_start, f_stop
        self.init_filter()
        
        self.channel_mask = np.ones(stream.nb_channel, dtype = bool)
        
        if autostart:
            self.start()
    
    def set_params(self, **kargs):
        for k, v in kargs.items():
            assert k in ['f_start', 'f_stop',]
            setattr(self, k, v)
        self.init_filter()
    
    def init_filter(self):
        sr = self.stream.sampling_rate
        Wn = [self.f_start/(sr/2.), self.f_stop/(sr/2.) ]
        if self.f_start>0. and self.f_stop<sr:
            print 'bandpass'
            self.b, self.a = scipy.signal.iirfilter(N=3, Wn=Wn, btype = 'bandpass', analog = False, ftype = 'butter', output = 'ba')
        elif self.f_start==0. and self.f_stop<sr:
            print 'lowpass'
            Wn = Wn[1]
            self.b, self.a = scipy.signal.iirfilter(N=3,  Wn=Wn, btype = 'lowpass', analog = False, ftype = 'butter', output = 'ba')
        elif self.f_start>0. and self.f_stop>=sr:
            print 'highpass'
            Wn = Wn[0]
            self.b, self.a = scipy.signal.iirfilter(N=3,  Wn=Wn, btype = 'highpass', analog = False, ftype = 'butter', output = 'ba')
        else:
            self.a, self.b = None, None
        self.zi = None
    
    def loop(self):
        port = self.stream['port']
        socket = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(port))
        
        out_socket = self.context.socket(zmq.PUB)
        out_socket.bind("tcp://*:{}".format(self.out_stream['port']))
        
        
        self.last_pos = None
        
        while self.running:
            events = socket.poll(50)
            if events ==0:
                time.sleep(.05)
                continue
            
            message = socket.recv()
            pos = msgpack.loads(message)
            if self.last_pos is None:
                self.last_pos = pos

            new = pos - self.last_pos
            if new==0: continue
            head = pos%self.half_size+self.half_size
            tail = head - new
            
            mask = self.channel_mask
            
            if self.a is None:
                filtered = self.in_array[mask,tail:head]
            else:
                if self.zi is None:
                    self.zi = np.array([ scipy.signal.lfilter_zi(self.b, self.a) for c in range(self.stream.nb_channel)])
                filtered, self.zi = scipy.signal.lfilter(self.b, self.a, self.in_array[mask, tail:head], axis = 1, zi = self.zi)

            head2 = pos%self.half_size
            tail2 = self.last_pos%self.half_size
            if tail2<head2:
                self.out_array[:,tail2:head2]= filtered
                self.out_array[:,tail2+self.half_size:head2+self.half_size] = filtered
            else:
                self.out_array[:,head2+self.half_size-new:head2+self.half_size] = filtered
                if tail2!=0:
                    self.out_array[:,-(self.half_size-tail2):] = filtered[:, :(self.half_size-tail2)]
                if head2!=0:
                    self.out_array[:,:head2] = filtered[:, -head2:]
            
            out_socket.send(msgpack.dumps(pos))
            self.last_pos = pos


