# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import msgpack
import pickle

import threading
import zmq

import time

import inspect

from collections import OrderedDict
from .tools import SharedArray
from .streamtypes import stream_type_list



"""




"""


class StreamHandler:
    """
    This class help to create new stream in a local process.
    It handle a list of streams.
    
    
    """
    def __init__(self, ):
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
    
    def get_stream_list(self):
        return self.streams
    
    def reset(self):
        self.streams = OrderedDict()


class StreamServer(StreamHandler):
    """
        This is like StreamHandler but also lanch a thread taht allow to create stream via other processes.
        
        Args : 
           * server_port: if not None (or 0) the handler lauch a thread with a socket
           
        
        The server part is via a socket and a pickled dict.
        
        request = { 'method' : 'get_stream_list', 'kargs' : { } } picklelized
        response = picklelized object return
        
    """
    def __init__(self, server_port = 12205):
        StreamHandler.__init__(self)
        
        self.latency = 50
        
        self.run = True
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:{}".format(server_port))
        self.thread = threading.Thread(target = self.server_loop)
        self.thread.start()
        
    
    
    def server_loop(self):
        while self.run:
            events = self.socket.poll(self.latency)
            if events ==0:
                time.sleep(self.latency/1000.)
                continue
            raw_req = self.socket.recv()
            req = pickle.loads(raw_req)
            
            if not( 'method' in req and 'kargs' in req):
                self.socket.send(pickle.dumps(None))
                continue
            if not hasattr(self,  req['method']):
                self.socket.send(pickle.dumps(None))
                continue
            print req['method']
            method = getattr(self, req['method'])
            print method
            if not inspect.ismethod(method):
                self.socket.send(pickle.dumps(None))
                continue
            raw_rep = method(**req['kargs'])
            print raw_rep
            
            stream = raw_rep[raw_rep.keys()[0]]
            #~ stream._params.pop('shared_array')
            print stream
            
            print 'sended'
            rep = pickle.dumps(raw_rep)
            self.socket.send(rep)
    
    def stop(self):
        self.run = False
        self.thread.join()

    #~ def __del__(self):
        #~ self.run = False
        #~ self.thread.join()

class StreamHandlerProxy:
    """
    Equivalent of streamhandler but this dialog with a StreamServer
    """
    def __init__(self, port = 12205):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:{}".format(port))
        
        class caller:
            def __init__(self, inst, methodname):
                self.inst = inst
                self.methodname = methodname
            def __call__(self,  **kargs):
                return self.inst.execute(  self.methodname, **kargs)
        
        methods = [ 'get_stream_list' ]
        methods.extend( 'new_'+stream_type.__name__ for  stream_type in stream_type_list)
        for method in methods:
            setattr(self, method, caller(self, method))
    
    
    
    def execute(self, method, **kargs):
        req = { 'method' : method, 'kargs' : kargs }
        self.socket.send(pickle.dumps(req))
        raw_ret = self.socket.recv() 
        ret = pickle.loads(raw_ret)
        return ret
        
        
        
    
    
        
        
        
        

