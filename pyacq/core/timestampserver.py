# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack

import gevent
import zmq.green as zmq
from collections import OrderedDict
from .tools import SharedArray

import time

class TimestampServer:
    """
    
    
    """
    def __init__(self):
        self.streams = OrderedDict()
        self.greenlets = OrderedDict()
        self.context = zmq.Context()
        
    def follow_stream(self, stream):
        port =  stream['port']
        self.streams[port] = stream
        
        stream['timestamp'] = SharedArray( shape = 10000, dtype = [('pos', np.uint64), ('time', np.float64)])
        stream['timestamp_pos'] = 0
        #~ print 'follow_stream', port
        self.greenlets[port] = gevent.spawn(self.start_loop, port)
        
        #np.datetime64(datetime.datetime.fromtimestamp(time.time()))
    
    def start_loop(self, port):
        socket = self.context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE,'')
        socket.connect("tcp://localhost:{}".format(port))
        stream = self.streams[port]
        timestamp = stream['timestamp'].to_numpy_array()
        #~ print 'start_loop follow', port
        while True:
            ts_pos = stream['timestamp_pos']%timestamp.shape[0]
            message = socket.recv()
            t = time.time()
            pos = msgpack.loads(message)
            timestamp[ts_pos] = (pos, t)
            stream['timestamp_pos'] += 1
            #~ print stream['timestamp_pos']
    
    def leave_stream(self, stream):
        port =  stream['port']
        self.streams.pop(port)
        self.greenlets[port].kill()
        
    def estimate_sampling_rate(self, port):
        # TODO take all point
        import scipy.stats
        if not port in self.streams : return
        stream = self.streams[port]
        
        timestamp = stream['timestamp'].to_numpy_array()
        ts_pos = stream['timestamp_pos']%timestamp.shape[0]
        
        if ts_pos>1:
            a,b,r,tt,stderr = scipy.stats.linregress(timestamp[:ts_pos]['pos'],timestamp[:ts_pos]['time'])
            return 1/a
        else:
            return 0.

