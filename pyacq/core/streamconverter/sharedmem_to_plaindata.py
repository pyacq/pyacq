# -*- coding: utf-8 -*-
"""


"""


import numpy as np
import zmq
import threading

import blosc


class AnaSigSharedMem_to_AnaSigPlainData:
    """
    This class take a AnalogSignalSharedMemStream and generate a AnalogSignalPlainDataStream.
    
    
    
    
    """
    def __init__(self, streamhandler,  shared_stream, paindata_port = None,
                                        info_port = None, autostart = True):
        self.sharedmem_stream = shared_stream
        self.streamhandler = streamhandler
        
        self.plaindata_stream = self.streamhandler.new_AnalogSignalPlainDataStream(port = paindata_port)
        
        self.context = zmq.Context()
        self.recv_socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE,'')
        self.socket.connect("tcp://localhost:{}".format(self.stream['port']))
        
        self.running = True
        
        if autostart:
            self.start()
    
    
    def start():
        self.thread_recv = thrading.Thread(target = self.recv_loop)
        
        self.thread_info = thrading.Thread(target = self.info_loop)
        
    
    
    
    def recv_loop(self):
        while self.running:
            message = self.recv_socket.recv()
            self.pos = msgpack.loads(message)
            self.newpacket.emit(self.port, self.pos)
            print pos
    
    def info_loop(self):
        pass

