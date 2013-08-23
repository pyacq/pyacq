# -*- coding: utf-8 -*-
"""


"""


import numpy as np
import zmq
import threading

import blosc
import msgpack

import time

class AnaSigPlainData_to_AnaSigSharedMem:
    """
    This class take a AnalogSignalPlainDataStream  and generate a AnalogSignalSharedMemStream.
    
    
    """
    def __init__(self, streamhandler,  plaindata_info_addr, buffer_length = 10.,
                                        autostart = True,):
        
        self.plaindata_info_addr = plaindata_info_addr
        self.streamhandler = streamhandler
        self.buffer_length = buffer_length
        
        self.running = True
        
        if autostart:
            self.start()
    
    
    def start(self):
        context = zmq.Context()
        
        
        ## get info on info socket
        info_socket = context.socket(zmq.REQ)
        
        info_socket.connect(self.plaindata_info_addr)
        info_socket.send('info_json')
        info = info_socket.recv_json()
        
        # create stream socket : send and recv
        kargs = dict(info)
        self.compress = kargs.pop('compress')
        kargs['buffer_length'] = self.buffer_length
        kargs['port'] = None
        self.sharedmem_stream = self.streamhandler.new_AnalogSignalSharedMemStream(**kargs)
        self.send_socket = context.socket(zmq.PUB)
        self.send_socket.bind("tcp://*:{}".format(self.sharedmem_stream['port']))
        
        self.recv_socket = context.socket(zmq.SUB)
        self.recv_socket.setsockopt(zmq.SUBSCRIBE,'')
        addr = self.plaindata_info_addr
        while not addr.endswith(':'):
            addr = addr[:-1]
        addr += str(info['port'])
        
        self.recv_socket.connect(addr)
        
        self.thread_recv = threading.Thread(target = self.recv_loop)
        self.thread_recv.start()



    def stop(self):
        self.running = False
        self.thread_recv.join()
    
    
    
    def recv_loop(self):
        
        np_array = self.sharedmem_stream['shared_array'].to_numpy_array()        
        half_size = np_array.shape[1]/2
        n = self.sharedmem_stream['nb_channel']
        while self.running:
            
            events = self.recv_socket.poll(50)
            if events ==0:
                time.sleep(.1)
                continue
            
            #~ print 'ici1'
            m0,m1 = self.recv_socket.recv_multipart()
            #~ print 'ici2'
            
            abs_pos = msgpack.loads(m0)
            
            if self.compress is None:
                buf = buffer(m1)
            elif self.compress == 'blosc':
                buf = blosc.decompress(m1)
            
            chunk = np.frombuffer(buf, dtype = np_array.dtype, ).reshape(-1, n).transpose()
            #~ print 'recv', abs_pos, chunk.shape
            
            new = chunk.shape[1]
            head = abs_pos%half_size+half_size
            tail = head - new
            np_array[:,  tail:head] = chunk
            head2 = abs_pos%half_size
            tail2 = max(head2 - new, 0)
            new2 = head2-tail2
            np_array[:,  tail:head] = chunk[:, -new2:]
            
            self.send_socket.send(msgpack.dumps(abs_pos))
            
            
            
            

    
    def info_loop(self):
        pass
        #self.channel_mask
